import tweepy
from time import sleep

auth = tweepy.OAuthHandler(credentials.consumer_key, credentials.consumer_secret)
auth.set_access_token(credentials.access_token, credentials.access_token_secret)
api = tweepy.API(auth)

'my_file=open('verne.txt','r')
'file_lines=my_file.readlines()
'my_file.close()

api.update_status("Hello world!")
