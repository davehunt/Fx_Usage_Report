import pyspark.sql.functions as F
from pyspark.sql.functions import lit, col, desc
from pyspark.sql import Window
import pandas as pd
import urllib
import json

def get_test_pilot_addons():
    '''
    Fetches all the live test pilot experiments listed in
    the experiments.json file. 
    
    returns a list of addon_ids
    '''
    url = "https://testpilot.firefox.com/api/experiments.json"
    response = urllib.urlopen(url)
    data = json.loads(response.read())
    all_tp_addons = ["@testpilot-addon"] + [i.get("addon_id") for i in data['results'] if i.get("addon_id")]
    return all_tp_addons


# grab all tp addons without a mozilla suffix
NON_MOZ_TP = [i for i in get_test_pilot_addons() if "@mozilla" not in i]

# this study is everywhere
UNIFIED_SEARCH_STR = '@unified-urlbar-shield-study-'

addon_filter = (~col('addon.is_system')) & (~col('addon.foreign_install')) & \
    (~col('addon.addon_id').isin(NON_MOZ_TP)) & (~col('addon.addon_id').like('%@mozilla%')) &\
    (~col('addon.addon_id').like('%@shield.mozilla%')) & (~col('addon.addon_id').like('%' + UNIFIED_SEARCH_STR + '%'))

    
def top10AddonsOnDate(data, date, topN, country_list):
    """ Gets the number of users in the past week who have used the top N addons,
        broken down by country.
        
        Parameters:
        data - The main ping server.
        date - The day you which you want to get the top N addons.
        topN - the number of addons to get.
        sc - A Spark context
        
        Returns:
        Dataframe containing the number of users using each of the addons.
    """
    if country_list is not None:
        data2 = data.drop('country').select('*', lit('All').alias('country'))
        data3 = data.filter(col('country').isin(country_list))\
                    .select('*', col('country').alias('country2'))\
                    .drop('country')\
                    .select('*', col('country2').alias('country'))\
                    .drop('country2')
        data = data2.union(data3)
    else:
        data = data.drop('country').select('*', lit('All').alias('country'))
        
    start_date = (date - pd.Timedelta(days=7)).strftime('%Y%m%d')

    wau = data.filter((col('submission_date_s3') > start_date) & 
                      (col('submission_date_s3') <= date.strftime('%Y%m%d')))\
            .groupBy('country')\
            .agg(lit(date.strftime('%Y%m%d')).alias('submission_date_s3'),
                 F.countDistinct('client_id').alias('wau'))
            
    counts = data.select('submission_date_s3', 'country', 
                         'client_id', F.explode('active_addons').alias('addon'))\
        .filter((col('submission_date_s3') > start_date) & 
                (col('submission_date_s3') <= date.strftime('%Y%m%d')))\
        .filter(addon_filter)\
        .select('country', 'client_id', 'addon.addon_id', 'addon.name')\
        .distinct()\
        .groupBy('country', 'addon_id')\
        .agg(F.count('*').alias('number_of_users'), F.last('name').alias('name'))\
        .select('*', lit(date.strftime('%Y%m%d')).alias('submission_date_s3'),
                lit(start_date).alias('start_date'),
                F.row_number().over(Window.partitionBy('country')\
                                      .orderBy(desc('number_of_users'))\
                                      .rowsBetween(Window.unboundedPreceding, Window.currentRow))
                              .alias('rank'))\
        .filter(col('rank') <= topN)\
        
    if country_list is not None:
        return counts.join(F.broadcast(wau), on = ['country'])\
            .select('country', 'submission_date_s3', 'start_date', 'addon_id', 'name', 
                    (col('number_of_users') / col('wau')).alias('percent_of_active_users'), 
                    'rank', 'number_of_users', 'wau')
    else:
        wau_num = wau.toPandas()['wau'][0]
        return counts.select('country', 'submission_date_s3', 'start_date', 'addon_id', 'name', 
                    (col('number_of_users') / wau_num).alias('percent_of_active_users'), 
                    'rank', 'number_of_users', lit(wau_num).alias('wau'))


def top10Addons(data, start_date, end_date, country_list, sc, topN = 10):
    """ Gets the number of users in the past week who have used the top N addons,
        broken down by country.
        
        Parameters:
        data - The main ping server
        start_date - The first day to get the top10Addons
        end_date - The last day to get the top10Addons
        sc - A spark context
        topN - the number of addons to get.
        
        Returns:
        Dataframe containing the number of users using each of the addons.
    """
    start_date = pd.to_datetime(start_date, format = '%Y%m%d')
    end_date = pd.to_datetime(end_date, format = '%Y%m%d')
    dates = pd.date_range(start_date, end_date, freq = '7D')

    outputs = [top10AddonsOnDate(data, date, topN, country_list) 
                   for date in dates]
    
    return sc.union([output.rdd for output in outputs]).toDF()