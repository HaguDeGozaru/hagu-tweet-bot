''' Refer to class HaguEigoBot '''
import os
import re
from shutil import copyfile
from time import sleep
import datetime
import json
from flags import Flags
import credentials
import tweepy

class FunctionFlags(Flags):
    __pickle_int_flags__ = True
    __no_flags_name__ = 'TweetOffline'
    __all_flags_name__ = 'Full'

class BotFunctions(FunctionFlags):
    """ Determines the functionality of a bot while running """
    #TODO: Finish implementation of function selection
    TweetTimed = 1
    Log = 2 #Unimplemented
    Interact = 4 #Unimplemented

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

    def __init__(self, functionality=0):
        """
        Create an instance of a HaguEigoBot,
        acquire authorization from Twitter (or run offline)
        """
        self.functionality = functionality
        self.authorization = None
        self.twitter_api = None
        #TODO: self.twitter_stream = None
        self.tweet_times = []
        self.feed_index = 0
        self.feed_length = 0
        self.min_tweet_delay = 10
        self.load_config() # Get tweeting times and current feed_index
        if functionality: #API is required
            self.authorization = tweepy.OAuthHandler(
                credentials.consumer_key, credentials.consumer_secret
            )
            self.authorization.set_access_token(
                credentials.access_token, credentials.access_token_secret
            )
            self.twitter_api = tweepy.API(self.authorization)
            if functionality > BotFunctions.TweetTimed: #Stream is required
                raise NotImplementedError("The Twitter stream functionality isn't ready yet.")
        else:
            self.min_tweet_delay = 2


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
            while feed_data[self.feed_index]['chain'] and self.feed_index < len(feed_data):
                print("Okay")
                self.feed_index += 1
                next_tweets.append(feed_data[self.feed_index]['tweet'])

            self.feed_index += 1 # Final increment
        return next_tweets

    def get_next_tweet_datetime(self):
        """ Gets the next datetime at which tweeting will occur. """
        if len(self.tweet_times) > 0:
            now_t = datetime.datetime.now()
            next_t = now_t
            if not self.functionality:
                #Don't use config's times if simulating
                return datetime.datetime.now() + datetime.timedelta(seconds=self.min_tweet_delay)

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
                print("Return now")
                return datetime.datetime.now()

            for time in self.tweet_times:
                # Pick apart time tuple, put in next_t
                next_t = next_t.replace(hour=time[0], minute=time[1])
                if now_t < next_t: # If next_t is in the future
                    return next_t.replace(second=0)

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
        for my_time in self.tweet_times:
            # Get next tweet ready
            next_index = self.feed_index + 1
            next_tweets = self.load_next_tweets()
            # Sleep until time in config
            delta = self.get_next_tweet_datetime() - datetime.datetime.now()
            print(self.get_next_tweet_datetime())
            print(datetime.datetime.now())
            print(delta.total_seconds())
            sleep(delta.total_seconds())
            for idx, tweet in enumerate(next_tweets):
                print('{} {} of {}'.format(tweet, next_index + idx, self.feed_length))
            if BotFunctions.TweetTimed in self.functionality:
                for tweet in next_tweets:
                    self.twitter_api.update_status(
                        '{}\n{} of {}'.format(tweet, next_index, self.feed_length)
                    )
                    next_index += 1
                    sleep(self.min_tweet_delay)

def main():
    """ Main body for starting up and terminating HaguEigoBot """
    # pylint: disable=no-member
    try:
        bot = HaguEigoBot(BotFunctions.TweetOffline)
        bot.start()

    except KeyboardInterrupt:
        print("Terminated at console.")

if __name__ == '__main__':
    main()
