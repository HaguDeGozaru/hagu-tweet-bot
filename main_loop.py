import tweepy
from credentials import *
from time import sleep

auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)
api = tweepy.API(auth)

'''
my_file=open('verne.txt','r')
file_lines=my_file.readlines()
my_file.close()
'''

api.update_status("Hello world!")
