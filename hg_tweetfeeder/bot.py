''' Module main class '''
import os
import logging
import datetime
import json
from time import sleep
from threading import Thread
from shutil import copyfile
from tweepy import API, StreamListener
from .file_io import LoadFromFile
from .config import Config
from .flags import BotFunctions, BotEvents
from .logs import log, log_setup

class TweetFeeder(StreamListener):
    """
    Dual-threaded bot to post tweets periodically,
    to track the tweets' performance, and to send alerts
    to / take commands from a master Twitter account.
    """
    def __init__(self, functionality=BotFunctions(), config=Config()):
        """
        Create a TweetFeeder bot,
        acquire authorization from Twitter (or run offline)
        """
        log_setup(
            True,
            config.filenames['log'] if (
                BotFunctions.LogToFile in functionality
                ) else "",
            TweetFeeder.LogSender(self.send_dummy_dm) if (
                BotFunctions.SendAlerts in functionality
                ) else None
        )

        self.functionality = functionality
        log(
            BotEvents.SYS.Setup,
            "{:-^80}".format(str(functionality) if functionality else "Offline testing")
        )

        self.config = config
        self.api = API(config.authorization)
        StreamListener.__init__(self.api)
        if(
                BotFunctions.TweetOffline in functionality or
                BotFunctions.TweetOnline in functionality
        ):
            self.running = True
            self._start_tweeting()

    class LogSender:
        """
        Acts as a delegate container so that the logger module
        can send log output over Twitter to the master account.
        """
        def __init__(self, send_method):
            ''' Attach the send_method that will be called for write() '''
            self.send_method = send_method

        def write(self, text):
            ''' If the text is substantial, forward it '''
            if len(text) > 1: #This prevents unnecessary terminators from being sent

                self.send_method(text)

    def send_dummy_dm(self, text):
        ''' Temporary implementation for sending logs over Twitter '''
        self.api.send_direct_message(user=self.config.master_id, text=text)

    def on_connect(self):
        """Called once connected to streaming server.

        This will be invoked once a successful response
        is received from the server. Allows the listener
        to perform some work prior to entering the read loop.
        """
        log(BotEvents.SYS.ThreadStart, "Streaming")

    def on_direct_message(self, status):
        """ Called when a new direct message arrives """
        try:
            if status.direct_message['sender_id'] != self.config.my_id:
                log(
                    BotEvents.NET.GetDM, "{}: {}".format(
                        status.direct_message['sender_screen_name'],
                        status.direct_message['text']
                        )
                    )
                return True
        except BaseException as my_event:
            log(BotEvents.DBG.Warn, str(my_event))

    def on_event(self, status):
        """ Called when a new event arrives.
        This responds to "favorite" and "quoted_tweet."
        """
        if status.event == "favorite": #This tends to come in delayed bunches
            log(
                BotEvents.NET.GetFavorite,
                "{}: {}".format(
                    status.source.screen_name,
                    status.target_object.id
                    )
            )
        elif status.event == "quoted_tweet":
            log(
                BotEvents.NET.GetQuoteRetweet,
                "{}: {}".format(
                    status.source['screen_name'],
                    status.target_object['text']
                    )
            )
        elif status.event == "unfavorite":
            pass #feed tracking only requires updating tweet stats based on current totals
        else:
            log(BotEvents.NET.GetUnknown, "on_event: " + status.event)

    def on_status(self, status):
        """ Called when a new status arrives. """
        if hasattr(status, 'retweeted_status'):
            log(
                BotEvents.NET.GetRetweet,
                "{}: {}".format(
                    status.user.screen_name,
                    status.retweeted_status.id
                    )
            )
        elif status.is_quote_status:
            pass #Ignore; this will be picked up by on_event
        elif status.in_reply_to_user_id == self.config.my_id:
            log(
                BotEvents.NET.GetReply,
                "{}: {}".format(
                    status.author.screen_name,
                    status.text
                    )
            )
        elif status.author.id == self.config.my_id and not status.in_reply_to_user_id:
            log(BotEvents.NET.SendTweet, status.id)
            #TODO: Register tweet in feed_tracking.json
        else:
            log(
                BotEvents.NET.GetUnknown,
                "on_status: " + str(status)
            )

    def on_disconnect(self, notice):
        """ Called when Twitter submits an error """
        log(BotEvents.SYS.ThreadStop, "Streaming: " + notice)
        self.running = False

    def get_next_tweet_datetime(self):
        """ Gets the next datetime at which tweeting will occur. """
        # Supply immediate times if no tweet times and tweeting offline
        if not self.config.tweet_times and BotFunctions.TweetOffline in self.functionality:
            return (
                datetime.datetime.now() +
                datetime.timedelta(seconds=self.config.min_tweet_delay*0.2)
            )
        # Offline or not, if there are tweet times, use them
        if self.config.tweet_times:
            final_time = self.config.tweet_times[-1]
            now_t = datetime.datetime.now()
            next_t = now_t.replace(
                hour=final_time[0],
                minute=final_time[1],
                second=0,
                microsecond=0)

            if now_t > next_t: #The final time lies before the current
                next_t = next_t + datetime.timedelta(days=1)

            for time in self.config.tweet_times:
                # Pick apart time tuple, put in next_t
                next_t = next_t.replace(hour=time[0], minute=time[1])
                if now_t < next_t: # If next_t is in the future
                    return next_t.replace(second=0)
        #Failure
        return None

    def update_feed_index(self, index):
        """ Wrapper for _save_tweet_data; updates feed index """
        self._save_tweet_data(index=index)

    def update_tweet_stats(self, tweet):
        """ Wrapper for _save_tweet_data; updates tweet stats """
        self._save_tweet_data(tweet=tweet)

    def _save_tweet_data(self, index=0, tweet=None):
        """ Saves the current feed index and altered tweet stats. """
        all_tweet_data = dict()
        #Prepare all_tweet_data; attempt to load existing data
        if os.path.exists(self.config.filenames['stats']): #Load existing data
            with open(self.config.filenames['stats'], 'r', encoding="utf8") as infile:
                all_tweet_data = json.load(infile)
            copyfile(self.config.filenames['stats'], self.config.filenames['stats'] + ".bak")
        else:
            all_tweet_data = {"feed_index": 0}
        #Edit all_tweet_data
        if BotFunctions.SaveTweetIndex in self.functionality and index > 0:
            all_tweet_data['feed_index'] = index
        if BotFunctions.SaveTweetStats in self.functionality and tweet:
            if tweet.author.id == self.config.my_id: #Bot tweeted this
                all_tweet_data['tweet_stats'][tweet.id]['title'] = tweet.title
        #Save all_tweet_data to config.filenames['stats']
        with open(self.config.filenames['stats'], 'w', encoding="utf8") as outfile:
            json.dump(all_tweet_data, outfile)

    def _start_tweeting(self):
        """ Begin normal functionality loop. """
        log(BotEvents.SYS.ThreadStart, "Tweet loop")
        self._tweet_thread = Thread(target=self._tweet_loop)
        self._tweet_thread.start()


    def _tweet_loop(self):
        """ Loop for tweeting, while the stream is open. """
        next_index = LoadFromFile.load_last_feed_index(self.config.filenames['stats'])

        while self.running:
            # Get next tweet(s) ready
            next_tweets, feed_length = (
                LoadFromFile.tweets_at(next_index, self.config.filenames['feed'])
            )
            next_index += 1

            if not next_tweets:
                log(BotEvents.SYS.ThreadStop, "Tweet loop: tweets_at() failed")
                self.running = False
                break

            # Sleep until time in config
            next_time = self.get_next_tweet_datetime()
            if next_time:
                delta = next_time - datetime.datetime.now()
            else:
                log(BotEvents.SYS.ThreadStop, "Tweet loop: get_next_tweet_datetime() failed")
                self.running = False
                break

            print("Wait for {} seconds".format(delta.total_seconds()))
            sleep(delta.total_seconds()) # > WAIT FOR NEXT TWEET TIME <<<<<<<<<<<<<<<<<<<<<<<<<<
            log_str = "{} tweet{} starting at {} ({})".format(
                len(next_tweets),
                's' if (len(next_tweets) > 1) else '',
                next_index,
                next_tweets[-1]['title']
                )
            log(BotEvents.SYS.LoadTweet, log_str)
            print(log_str)

            # Submit each tweet in chain (or just one, if not a chain)
            if BotFunctions.TweetOnline in self.functionality:
                for tweet in next_tweets:
                    self.api.update_status(
                        '{}\n{} of {}'.format(tweet['text'], next_index, feed_length)
                    )
                    next_index += 1
                    sleep(self.config.min_tweet_delay.TWEET_DELAY)
            self.update_feed_index(next_index)
        # Running loop ended
        log(BotEvents.SYS.ThreadStop, "Tweet loop ended.")
