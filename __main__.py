''' Main executable for the "hg_tweetfeeder" Twitter bot. '''

from hg_tweetfeeder import TweetFeeder, BotFunctions, BotEvents
from tweepy import Stream

def main():
    """ Main body for starting up and terminating Tweetfeeder bot """
    # pylint: disable=no-member
    try:

        bot = TweetFeeder(BotFunctions.TweetOnline|BotFunctions.LogEvents)
        stream = Stream(bot.config.authorization, bot)
        if BotFunctions.WatchUserStream in bot.functionality:
            stream.userstream()

    except KeyboardInterrupt:
        bot.log_event(BotEvents.SYS_Stop, "Terminated at console.")
        bot.disconnect()

if __name__ == "__main__":
    main()
