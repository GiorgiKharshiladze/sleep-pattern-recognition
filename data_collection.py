import pandas as pd, numpy as np
import glob, datetime, json, re, subprocess

keys = json.loads(open('keys.json').read())

# DATA IMPORTER
# ================================================================================
def import_dataframes(amount="*"):
    """Function that concatinates all data and returns the big df"""
    all_frames = []
    counter = 0
    for date in get_existing_days():
        all_frames.append(pd.read_csv('data/alta_hr/'+date+".csv", index_col="datetime"))
        counter += 1
        if amount != "*":
            if counter == amount:
                break
    merged_df = pd.concat(all_frames, sort=True)
    merged_df['time'] = merged_df.index
    merged_df['time'] = merged_df['time'].apply(lambda x: datetime_str_into_seconds(x))
    return merged_df[['time','heart_rate','half_mins_passed','activity','mets','calories','sleep_stage']]

# ================================================================================

# DATA UPDATER
# ================================================================================
def update_data_files():
    """Funtion that downloads the most recent csv files in the data directory"""
    for date in get_missing_days():
        try:
            if len(get_dataframe(date)) != 0: # if dataframe is not empty for this date
                get_dataframe(date).to_csv("data/alta_hr/"+date+".csv")
                print("Updated datafile for "+ str(date))

        except:
            print("Cannot update data for "+str(date))
# ================================================================================


# DATA GATHERING FROM THE API
# ================================================================================
def get_data_from_server(date, data_type):
    """Calling subprocess to retrieve the data from fitbit api"""
    get = keys['API_URL'] # api base url
    if data_type == "heart":
        get += "activities/heart/date/"+date+"/1d/1sec.json"
    elif data_type == "sleep":
        get += "sleep/date/"+date+".json"
    elif data_type == "calories":
        get += "activities/calories/date/"+date+"/1d.json"

    output = subprocess.check_output(["curl","-i","-H", keys["AUTH"], get]).decode('ascii')
    
    return json_from_str(output) # return only json object output from the string data

def get_heart_rate_data(date):
    """Returns the dictionary of {time, heart_rate} for the given date"""
    times, heart_rates = [], []
    # get heart data from the data file
    data = get_data_from_server(date, "heart")
    for item in data['activities-heart-intraday']['dataset']:
        times.append(datetime_str_to_object(date+"T"+item['time']+".000"))
        heart_rates.append(item['value'])
            
    return {'time':times, 'heart_rate':heart_rates}

def get_activity_data(date):
    activity, mets, times, calories = [], [], [], []
    data = get_data_from_server(date,"calories")
    
    for item in data['activities-calories-intraday']['dataset']:
        current_time = datetime_str_to_object(date+"T"+item['time']+".000")
        times.append(current_time)
        times.append(current_time + datetime.timedelta(seconds=30))
        activity.append(item['level'])
        activity.append(item['level'])
        mets.append(item['mets']/2)
        mets.append(item['mets']/2)
        calories.append(item['value']/2)
        calories.append(item['value']/2)
        
    return {"time":times, "activity":activity, "mets":mets, "calories":calories}

def get_dataframe(date):
    """Returns the df of time(index), heart_rate, sleep_stage, half_mins_passed"""
    # create pandas dataframe from json, resample 30 seconds and write mean(integer) of heart rates
    df_heart = pd.DataFrame(get_heart_rate_data(date)).set_index('time').resample('30s').mean().fillna(0).astype(int) # heart rate df
    df_activity = pd.DataFrame(get_activity_data(date)).set_index('time') # activity df
    df = df_heart.join(df_activity)
    clean_df = pd.DataFrame(columns=['heart_rate','sleep_stage','half_mins_passed', 'activity', 'mets', 'calories'])

    # get sleep data from the data file
    data = get_data_from_server(date, "sleep")
    for sleep in data['sleep']:
        if sleep['type'] == "stages": # get the detailed sleeps as many as there are in 24hrs
            start_time = datetime_str_to_object(sleep['startTime'])# sleep start time
            end_time = datetime_str_to_object(sleep['endTime'])# sleep end time
            
            # get only sleep time heart rate data from the entire day heart rate data
            clean_df = clean_df.append(df.loc[start_time:end_time,], sort=True)
            for item in sleep['levels']['data']:
                clean_df.loc[datetime_str_to_object(item['dateTime']), 'sleep_stage'] = item['level']
            clean_df['datetime'] = clean_df.index # create a datetime column that is equal to index
            clean_df = clean_df.fillna(method='ffill') # forward fill the sleep stages in-between
            # generate the amount of 30 seconds passed based on the time and sleep start_time
            clean_df.loc[clean_df['half_mins_passed'].isnull(), 'half_mins_passed'] = clean_df.apply(lambda x: (x['datetime']-start_time).total_seconds()//30, axis=1)
            clean_df['half_mins_passed'] = clean_df['half_mins_passed'].astype(int)  # convert column to int
            clean_df.index.name='datetime' # name our index as datetime
    
    return clean_df #returns empty list if no detailed sleep found

# HELPERS
# ================================================================================
def json_from_str(s):
    """Helper function to match json object from the string data"""
    match = re.findall(r"{.+[:,].+}|\[.+[,:].+\]", s)
    return json.loads(match[0]) if match else None

def datetime_str_to_object(fitbit_str):
    """Helper function to convert fitbit datetime str into python datetime object"""
    return datetime.datetime.strptime(fitbit_str, "%Y-%m-%dT%H:%M:%S.000")

def datetime_str_into_seconds(datetime_str):
    time = datetime.datetime.strptime(datetime_str,"%Y-%m-%d %H:%M:%S").time()
    return (time.hour * 60 + time.minute) * 60 + time.second
    
def get_existing_days():
    """Helper function to get the existing dates from the data directory"""
    existing_days = []
    for i in glob.glob('data/alta_hr/*.csv'):
        existing_days.append(i[13:23]) # get existing days from the data
    return sorted(existing_days)

def get_num_days():
    return len(get_existing_days())

def get_missing_days():
    """Helper function to get the missing dates from the data directory"""
    missing_days = []
    existing_days = get_existing_days()
    # sort and get the most recent date
    last_updated = datetime.datetime.strptime(sorted(existing_days, key=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d'))[-1], '%Y-%m-%d')
    # find the missing days till today
    for i in range((datetime.datetime.today()-last_updated).days):
        missing_days.append((datetime.datetime.today() - datetime.timedelta(days=i)).strftime('%Y-%m-%d'))
    return missing_days