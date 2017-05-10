''' Refer to class HaguEigoBot '''
import os
import re
from shutil import copyfile
from time import sleep
import datetime
import json
import credentials
import tweepy

'''
authorization = tweepy.OAuthHandler(consumer_key, consumer_secret)
authorization.set_access_token(access_token, access_token_secret)
twitter = tweepy.API(auth)
'''
'''twitter.update_status('Hello world!')'''
class HaguEigoBot:
    '''
    While running, refreshes a JSON feed and settings file periodically
    so as to deliver content to Twitter. Also, responds to Twitter inputs.
    Requires: credentials.py, config.json, feed.json
    Will create output.json if it doesn't exist already, to track place in feed and current version
    '''
    FEED = "feed.json"
    CONFIG = "config.json"
    OUTPUT = "output.json"
    OUTPUT_BACKUP = "output.json.bak"

    def __init__(self, run_offline):
        """
        Create an instance of a HaguEigoBot,
        acquire authorization from Twitter (or run offline)
        """
        self.authorization = None
        self.twitter = None
        self.tweet_times = []
        self.feed_index = 0
        self.feed_length = 0
        if run_offline != True:
            self.authorization = tweepy.OAuthHandler(
                credentials.consumer_key, credentials.consumer_secret
            )
            self.authorization.set_access_token(
                credentials.access_token, credentials.access_token_secret
            )
            self.twitter = tweepy.API(self.authorization)
        self.load_config()

    def load_config(self):
        """
        Loads config settings and attempts to
        resume the last session using output.json.
        """
        with open(HaguEigoBot.CONFIG) as config_json:
            config = json.load(config_json)
            print(config)
            for time_str in config['tweet_times']:
                self.tweet_times.append(
                    [int(x) for x in re.search(r'0?([12]?\d):0?([1-5]?\d)', time_str).groups()]
                )
            print(self.tweet_times)
        #TODO: Load output.json and set feed_index to resume from last session

    def load_next_tweets(self):
        """ Loads feed data necessary for the next tweet batch. """
        print("Current feed index = " + str(self.feed_index))
        next_tweets = []
        with open(HaguEigoBot.FEED) as feed_json:
            feed_data = json.load(feed_json)
            self.feed_length = len(feed_data)
            if self.feed_index > len(feed_data):
                return None
            next_tweets.append(feed_data[self.feed_index]['tweet'])
            print(feed_data[self.feed_index]['chain'])
            while feed_data[self.feed_index]['chain'] and self.feed_index > len(feed_data):
                print("Okay")
                self.feed_index += 1
                next_tweets.append(feed_data[self.feed_index]['tweet'])
            
            self.feed_index += 1 # Final increment
        return next_tweets

    def get_next_tweet_datetime(self):
        """ Gets the next datetime at which tweeting will occur. """
        if len(self.tweet_times) > 0:
            now_t = datetime.datetime.today()
            next_t = now_t
            if (
                    self.tweet_times[-1][0] < now_t.hour or
                    (
                        self.tweet_times[-1][0] == now_t.hour and
                        self.tweet_times[-1][1] < now_t.minute
                    )
                ): #Add a day if it's too late
                next_t = next_t + datetime.timedelta(days=1)
                print("Trying tomorrow")
            elif (
                    self.tweet_times[-1][0] == now_t.hour and
                    self.tweet_times[-1][1] == now_t.minute
                ):
                # DO IT NOW!!
                return datetime.datetime.today()

            for time in self.tweet_times:
                # Pick apart time tuple, put in next_t
                next_t = next_t.replace(hour=time[0], minute=time[1])
                if now_t < next_t: # If next_t is in the future
                    return next_t

        #No viable times were found
        return None

    def write_report(self):
        """ Writes to output.json to save progress and action log. """
        all_log_data = None
        if os.path.exists(HaguEigoBot.OUTPUT):
            with open(HaguEigoBot.OUTPUT, 'r') as output_json:
                all_log_data = json.load(output_json)
            copyfile(HaguEigoBot.OUTPUT, HaguEigoBot.OUTPUT_BACKUP)
            os.remove(HaguEigoBot.OUTPUT)
        #TODO Add new log data to 'all log data', flush log
        with open(HaguEigoBot.OUTPUT, 'w') as output_json:
            json.dump(all_log_data, output_json, indent=4)

    def start(self):
        """ Begin normal functionality loop. """
        # Currently only runs through tweet times.
        for i in range(len(self.tweet_times)):
            # Get next tweet ready
            next_index = self.feed_index + 1
            next_tweets = self.load_next_tweets()
            # Sleep until time in config
            delta = self.get_next_tweet_datetime() - datetime.datetime.now()
            sleep(delta.total_seconds())
            for tweet in next_tweets:
                print('{} {} of {}'.format(tweet, next_index, self.feed_length))
            if self.twitter:
                for tweet in next_tweets:
                    self.twitter.update_status(
                        '{}\n{} of {}'.format(tweet, next_index, self.feed_length)
                    )
                    next_index += 1
                    sleep(5)

            #now = datetime.datetime.today()
            #datetime.date

bot = HaguEigoBot(True)
bot.start()
