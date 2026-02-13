# Mashup Project

This project creates a mashup by downloading videos, extracting audio, trimming, and merging.

Live URL:
https://mashup-project-5wey.onrender.com

## How 102303229.py works

Steps:
1. Search and download $N$ YouTube videos for the singer.
2. Convert the downloads to mp3 audio.
3. Trim the first $Y$ seconds from each audio.
4. Merge all trimmed audio into one output file.

Command line usage:
```
python 102303229.py "Singer Name" <NumberOfVideos> <AudioDurationSec> <OutputFile.mp3>
```

Example:
```
python 102303229.py "The Weeknd" 12 30 output.mp3
```

Constraints:
- Number of videos must be greater than 10.
- Duration must be greater than 20 seconds.

## Web App

Run locally:
```
python app.py
```

Open:
http://127.0.0.1:5000

The form asks for singer name, number of videos, duration, and email. The result is emailed as a zip file.


