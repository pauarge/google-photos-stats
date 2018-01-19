import pickle
import argparse

import httplib2
import os

import matplotlib.pyplot as plt
import flatten_dict

from collections import defaultdict

from apiclient import discovery
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage

flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()

# If modifying these scopes, delete your previously saved credentials
# at ~/.credentials/drive-python-quickstart.json
SCOPES = 'https://www.googleapis.com/auth/drive.metadata.readonly'
CLIENT_SECRET_FILE = 'data/client_secret.json'
APPLICATION_NAME = 'Google Photos Stats'
PAGE_SIZE = 1000


def get_credentials():
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """
    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir, 'google-photos-stats.json')

    store = Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        credentials = tools.run_flow(flow, store, flags)
        print('Storing credentials to ' + credential_path)
    return credentials


class Parser(object):
    def __init__(self):
        credentials = get_credentials()
        http = credentials.authorize(httplib2.Http())
        self.service = discovery.build('drive', 'v3', http=http)

        # List of tuples (Google ID, filename)
        self.images_preloaded = False
        self.cameras_preloaded = False
        self.images = self.load_images()
        self.cameras = self.load_cameras()
        self.items_listed = 0
        self.processed_images = 0

        # Multithreading
        # self.executor = concurrent.futures.ThreadPoolExecutor(1)
        # self.futures = []

    def process_page(self, next_page=None):
        if not self.images_preloaded:
            results = self.service.files().list(q="mimeType contains 'image/'", pageSize=PAGE_SIZE, pageToken=next_page,
                                                fields="nextPageToken, files(id, name)").execute()
            items = results.get('files', [])
            if not items:
                print('No files found.')
            else:
                for item in items:
                    self.images.append((item['id'], item['name']))
                self.items_listed += len(items)
                print("Processed {} items".format(self.items_listed))
                if results.get('nextPageToken'):
                    self.process_page(results.get('nextPageToken'))
                else:
                    self.images_preloaded = True

    def process_images(self):
        if not self.cameras_preloaded:
            total = len(self.images)
            for google_id, name in self.images:
                self.process_image(google_id, total)
                # self.futures.append(self.executor.submit(self.process_image, gId, total))
            # concurrent.futures.wait(self.futures)
            self.dump_cameras()
            self.cameras_preloaded = True

    def process_image(self, google_id, total):
        meta = self.service.files().get(fileId=google_id, fields="imageMediaMetadata").execute()
        image_media_metadata = meta.get('imageMediaMetadata')
        if image_media_metadata:
            make = image_media_metadata.get('cameraMake')
            model = image_media_metadata.get('cameraModel')
            if make and model:
                self.cameras[make][model] += 1
        self.processed_images += 1
        print("Processed {} of {} images".format(self.processed_images, total))

    def load_images(self):
        if os.path.exists('data/images.pckl'):
            with open('data/images.pckl', 'rb') as f:
                self.images_preloaded = True
                return pickle.load(f)
        else:
            return []

    def load_cameras(self):
        if os.path.exists('data/cameras.pckl'):
            with open('data/cameras.pckl', 'rb') as f:
                self.cameras_preloaded = True
                return pickle.load(f)
        else:
            return defaultdict(lambda: defaultdict(int))

    def dump_images(self):
        with open('data/images.pckl', 'wb') as f:
            pickle.dump(self.images, f)

    def dump_cameras(self):
        with open('data/cameras.pckl', 'wb') as f:
            pickle.dump(dict(self.cameras), f)

    def get_images(self):
        print("Images")


def space_reducer(k1, k2):
    if k1 is None:
        return k2
    else:
        return k1 + " " + k2


def generate_graphic(cameras):
    cameras_flattened = flatten_dict.flatten(cameras, reducer=space_reducer)
    print(cameras_flattened)

    fig = plt.figure()
    plt.grid(True)
    plt.bar(range(len(cameras_flattened)), list(cameras_flattened.values()), align='center')
    plt.xticks(range(len(cameras_flattened)), list(cameras_flattened.keys()))
    fig.autofmt_xdate()
    plt.show()


def main():
    parser = Parser()
    parser.process_page()
    parser.dump_images()
    parser.process_images()
    generate_graphic(parser.cameras)


if __name__ == '__main__':
    main()
