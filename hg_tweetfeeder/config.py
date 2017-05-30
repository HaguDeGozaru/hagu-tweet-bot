''' Compile-time configuration data for hg_tweetfeeder.bot '''

from re import search
from tweepy import OAuthHandler
from .file_io import LoadFromFile

class Config:
    ''' Config data storage and processing for usage inside hg_tweetfeeder.bot '''
    def __init__(self):
        # EDIT THESE
        tweet_time_strings = ['12:02']
        self.min_tweet_delay = 10
        self.filenames = {
            "feed" : "./feeds/tweet_feed.json",
            "stats" : "./feeds/tweet_stats.json",
            "log" : "./logs/bot_events.log",
            "auth" : "./private/credentials.json"
        }
        # DO NOT EDIT THESE
        creds = LoadFromFile.get_json_dict(self.filenames['auth'])
        self.authorization = Config.auth_from_keys(**creds['authorization'])
        self.my_id, self.master_id = creds['twitter_ids'].values()
        self.tweet_times = Config.parse_tweet_times(tweet_time_strings)

    @staticmethod
    def auth_from_keys(consumer_key, consumer_secret, access_token, access_token_secret):
        ''' Creates an authorization handler from credentials '''
        authorization = OAuthHandler(
            consumer_key, consumer_secret
        )
        authorization.set_access_token(
            access_token, access_token_secret
        )
        return authorization

    @staticmethod
    def parse_tweet_times(tt_list):
        ''' Converts easily read times into useful ints. '''
        tweet_times = []
        for time_str in tt_list:
            tweet_times.append(
                [int(x) for x in search(r'0?([12]?\d):0?([1-5]?\d)', time_str).groups()]
            )
        return tweet_times
