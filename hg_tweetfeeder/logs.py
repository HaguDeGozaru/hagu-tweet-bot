''' Logging for bot.py '''
import logging
from .flags import BotEvents

BOT_LOGGER = logging.getLogger('hg_tweetfeeder.bot')

class KeywordFilter(logging.Filter):
    ''' Allows emission of records with given keywords. '''
    def __init__(self, keyword_list):
        ''' Acquires a list of keywords to check records with '''
        self.keywords = keyword_list
        logging.Filter.__init__(self)

    def filter(self, record):
        ''' Checks the record for keywords. '''
        if any(keyword in record.msg for keyword in self.keywords):
            return True
        return False

def log_setup(console_output=True, log_file="", net_stream=None):
    """
    Automatically executed method to set up logging.
    TODO: Export the setup process to a file in /logs
    """
    BOT_LOGGER.setLevel(logging.INFO)

    console_handler = logging.StreamHandler() #Defaults to sys.stderr, never disabled
    file_handler = logging.FileHandler(log_file, encoding='utf8')
    net_handler = logging.StreamHandler(net_stream)

    console_handler.setFormatter(
        logging.Formatter('%(asctime)s %(message)s', '%m/%d %H:%M')
    )
    file_handler.setFormatter(
        logging.Formatter('%(asctime)s %(levelname)-8s %(message)s', '%m/%d/%y %H:%M:%S')
    )
    net_handler.setFormatter(
        logging.Formatter('%(name)s %(message)s')
    )
    net_handler.addFilter(
        KeywordFilter(
            [
                str(BotEvents.NET.GetReply),
                str(BotEvents.NET.GetQuoteRetweet)
            ]
        )
    )

    if console_output:
        BOT_LOGGER.addHandler(console_handler)
    if log_file:
        BOT_LOGGER.addHandler(file_handler)
    if net_stream:
        BOT_LOGGER.addHandler(net_handler)

def log(ev_type=BotEvents.DBG.Warn, message=""):
    ''' Wrapper for the logging module's log methods. '''
    text = "{:<18}: {}".format(ev_type, message)
    if ev_type.value in BotEvents.SeverityRange.Info:
        BOT_LOGGER.info(text)
    elif ev_type.value in BotEvents.SeverityRange.Warn:
        BOT_LOGGER.warning(text)
    elif ev_type.value in BotEvents.SeverityRange.Err:
        BOT_LOGGER.error(text)
    else:
        print("-- CRITICAL --")
        BOT_LOGGER.critical(text)

    return True
