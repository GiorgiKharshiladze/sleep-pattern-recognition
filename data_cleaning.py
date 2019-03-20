import pandas as pd, numpy as np, json, datetime

def datetime_str_to_object(fitbit_str):
    """Helper function to convert fitbit datetime str into python datetime object"""
    return datetime.datetime.strptime(fitbit_str, "%Y-%m-%dT%H:%M:%S.000")

def get_heart_rate_data(date):
    """Returns the dictionary of {time, heart_rate} for the given date"""
    times, heart_rates = [], []
    # get heart data from the data file
    with open('data/alta_hr/'+date+'-heart.json') as file:
        data = json.load(file)
        for item in data['activities-heart-intraday']['dataset']:
            times.append(datetime_str_to_object(date+"T"+item['time']+".000"))
            heart_rates.append(item['value'])
            
    return {'time':times, 'heart_rate':heart_rates}

def get_dataframe(date):
    """Returns the df of time(index), heart_rate, sleep_stage, half_mins_passed"""
    # create pandas dataframe from json, resample 30 seconds and write mean(integer) of heart rates
    df = pd.DataFrame(get_heart_rate_data(date)).set_index('time').resample('30s').mean().fillna(0).astype(int)
    df['sleep_stage'] = np.nan # fill sleep_stages with nan values
    
    # get sleep data from the data file
    with open('data/alta_hr/'+date+'-sleep.json') as file:
        data = json.load(file)
        start_time = datetime_str_to_object(data['sleep'][0]['startTime']) # sleep start time
        end_time = datetime_str_to_object(data['sleep'][0]['endTime']) # sleep end time
        for item in data['sleep'][0]['levels']['data']:
            df.loc[datetime_str_to_object(item['dateTime']), 'sleep_stage'] = item['level']
            
    df = df.loc[start_time:end_time,].fillna(method='ffill')
    df['half_mins_passed'] = np.arange(len(df))
    
    return df[['half_mins_passed','heart_rate','sleep_stage']] # correct order

import subprocess, json, re

def json_from_str(s):
    match = re.findall(r"{.+[:,].+}|\[.+[,:].+\]", s)
    return json.loads(match[0]) if match else None

def get_data_from_server():
    get = "https://api.fitbit.com/1/user/-/activities/heart/date/2019-03-19/1d/1min.json"
    output = subprocess.check_output(["curl","-i","-H","Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiIyMkRLVzciLCJzdWIiOiI3RDk3UE0iLCJpc3MiOiJGaXRiaXQiLCJ0eXAiOiJhY2Nlc3NfdG9rZW4iLCJzY29wZXMiOiJ3aHIgd3BybyB3bnV0IHdzbGUgd3dlaSB3c29jIHdhY3Qgd3NldCB3bG9jIiwiZXhwIjoxNTUzNjQwNTIxLCJpYXQiOjE1NTMwMzU3MjF9.9HpnA3fFwMp--6VKXjYVMetocHUPkETx43AQCDURnNE", get]).decode('ascii')
    
    return json_from_str(output)