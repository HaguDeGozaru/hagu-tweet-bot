''' Compile-time configuration data for hg_tweetfeeder.bot '''

import json

class LoadFromFile:
    ''' Collection of static methods for getting stuff out of files. '''
    @staticmethod
    def get_json_dict(filename):
        ''' Returns the entire JSON dict in a given file. '''
        with open(filename, encoding="utf8") as infile:
            return json.load(infile)

    @staticmethod
    def tweets_at(feed_index, filename):
        """
        Loads a tweet or chain of tweets at feed_index
        and returns them along with the total tweets available.
        """
        next_tweets = []
        feed_data = LoadFromFile.get_json_dict(filename)
        feed_length = len(feed_data)
        if feed_index >= feed_length:
            return (None, feed_length)
        next_tweets.append(feed_data[feed_index])
        while feed_data[feed_index]['chain'] and feed_index < len(feed_data):
            feed_index += 1
            next_tweets.append(feed_data[feed_index])

        return (next_tweets, feed_length)

    @staticmethod
    def load_last_feed_index(filename):
        """
        Loads the feed index saved from a previous session if
        feed stats exist
        """
        stats = LoadFromFile.get_json_dict(filename)
        if stats:
            return stats['feed_index']

        return 0
