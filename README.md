# FaceCheck

FaceCheck is a Chrome extension which runs passively on popular dating websites automatically alerting the user of profiles which are potentially fraudulent. FaceCheck works by scraping the name and image presented on the profile page currently being viewed. This image is then queried on a user database of both fraudulent and non fraudulent user entries. If a match is found on a fraudulent entry the user is notified that the profile is possibly fraudulent, if the image isn't found on the database listed to a fraudulent user the image is then queried on 3 reverse image search engines, Google, Yandex and Tineye. Any pages found from these search engines which feature the profile image are checked to see if they in they contain the name listed on the profile or a scam related word. If the profile name is not present or a scam related word is present the profile is flagged up as potentially fraudulent and the user is notified, providing links to the website(s) which were flagged as suspicious that so that the user can investigate further. 

## Usage

To use FaceCheck first download this repository. Once FaceCheck is downloaded onto your device load the extension into Google Chrome by going to chrome://extensions/ pressing the 'Load unpacked' button and selecting the FaceCheck folder. Start the server by navigating to the FaceCheck directory and running 'python3 FaceCheck_server.py'. Once these steps have been completed and the FaceCheck extension is turned on in Chrome FaceCheck should now be running in-browser. 

Please note to allow results to be gathered from the Google Vision API you will require authentification, please refer to: https://cloud.google.com/docs/authentication
