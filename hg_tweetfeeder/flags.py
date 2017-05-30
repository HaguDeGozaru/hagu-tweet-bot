''' Classifications for bot functionality and events '''

from enum import Enum
from flags import Flags

class BotFunctions(Flags):
    """ Determines the functionality of a bot while running """
    #Basic offline functionality
    LogToFile = 1            #Write to event log file
    TweetOffline = 2        #Run through tweets offline, merely printing them
    SaveTweetIndex = 4      #Save tweeting progress in feed tracking JSON
    TweetOnline = 8         #Tweet from feed_log (requires config.json)
    WatchUserStream = 16    #Pull events from stream.userstream
    SaveTweetStats = 32     #Save tweet IDs as they're tweeted plus...
                            #...stats collected from stream.track
    SendAlerts = 64           #Unimplemented
    Everything = 127
    TestStreamsOnly = 1+16+64


class BotEvents:
    ''' Event codes for saving to output JSON '''
    class SeverityRange:
        ''' Ranges to supply logging module with severity. '''
        Info = range(0, 100)
        Warn = range(100, 200)
        Err = range(200, 300)

    class SYS(Enum):
        ''' System events: start, stop, file io '''
        Setup = 1
        ThreadStart = 2
        ThreadStop = 3
        Command = 4
        LoadTweet = 5
        ShutDown = 6
        StoppedByKeyboard = 190
        NoTweetsFound = 110
        NoTimesFound = 120

    class NET(Enum):
        ''' Events that happen on Twitter '''
        SendTweet = 6
        SendReply = 7
        SendDM = 8
        GetRetweet = 10
        GetQuoteRetweet = 11
        GetReply = 12
        GetDM = 13
        GetFavorite = 14
        GetUnknown = 101

    class DBG(Enum):
        ''' Debug (not yet handled) events '''
        Info = 0
        Warn = 100
        Err = 200
