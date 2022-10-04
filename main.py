import datetime
import srt
import os
from google.cloud import speech_v1
from google.cloud import storage

"""
    Place the video file which you want to extract the audio from in to same directory as this file.
    
    Give the file name of the video file, including the extension (.mp4) into this function as the video_file parameter.
    Give your subtitle file a name, such as "temp_subtitle" WITHOUT the (.srt)
    
    This will then generate a subtitle file for this videos' audio.
"""
def generate_subtitles(video_file, subtitle_filename):
    print("extracting audio from video..")
    audioCodec = "wav"
    tempAudioFilename = "temp_audio.{}".format(audioCodec)
    ffmpegExtractAudioCmd = "ffmpeg -loglevel warning -y -i {} -vn -ac 1 {}".format(video_file, tempAudioFilename)
    os.system(ffmpegExtractAudioCmd)
    print("extracted audio successfully")

    # Instantiates a client
    storage_client = storage.Client.from_service_account_json("config.json")
    bucket_name = "temp-audio-storage"
    bucket = storage_client.get_bucket(bucket_name)

    # # push this audio file to google cloud storage
    print("uploading to google cloud storage.. please wait")
    tempAudioBlob = bucket.blob(tempAudioFilename)
    tempAudioBlob.upload_from_filename(tempAudioFilename, timeout=500)
    print("upload complete")

    print("starting to analyze audio for text.. please wait, this could take time (especially if its a long video)")
    client = speech_v1.SpeechClient.from_service_account_json("config.json")

    config = speech_v1.RecognitionConfig(dict(
        enable_word_time_offsets=True,
        enable_automatic_punctuation=True,
        speech_contexts=[speech_v1.SpeechContext(dict(phrases="one perfect speech"))],
        language_code="en-US",
        model="video",
        use_enhanced=True)
    )

    audio = speech_v1.RecognitionAudio(dict(
        uri="gs://{}/{}".format(bucket_name, tempAudioFilename)
    ))

    operation = client.long_running_recognize(config=config, audio=audio)
    response = operation.result()

    bin_size = 3
    transcriptions = []
    index = 0

    for result in response.results:
        try:
            if result.alternatives[0].words[0].start_time.seconds:
                # bin start -> for first word of result
                start_sec = result.alternatives[0].words[0].start_time.seconds
                start_microsec = result.alternatives[0].words[0].start_time.seconds * 1000
            else:
                # bin start -> For First word of response
                start_sec = 0
                start_microsec = 0

            end_sec = start_sec + bin_size  # bin end sec

            # for last word of result
            last_word_end_sec = result.alternatives[0].words[-1].end_time.seconds
            last_word_end_microsec = result.alternatives[0].words[-1].end_time.seconds * 1000

            # bin transcript
            transcript = result.alternatives[0].words[0].word

            index += 1  # subtitle index

            for i in range(len(result.alternatives[0].words) - 1):
                try:
                    word = result.alternatives[0].words[i + 1].word
                    word_start_sec = result.alternatives[0].words[i + 1].start_time.seconds
                    word_start_microsec = result.alternatives[0].words[
                                              i + 1].start_time.seconds * 1000  # 0.001 to convert nana -> micro
                    word_end_sec = result.alternatives[0].words[i + 1].end_time.seconds

                    if word_end_sec < end_sec:
                        transcript = transcript + " " + word
                    else:
                        previous_word_end_sec = result.alternatives[0].words[i].end_time.seconds
                        previous_word_end_microsec = result.alternatives[0].words[i].end_time.seconds * 1000

                        # append bin transcript
                        transcriptions.append(srt.Subtitle(index, datetime.timedelta(0, start_sec, start_microsec),
                                                           datetime.timedelta(0, previous_word_end_sec,
                                                                              previous_word_end_microsec), transcript))

                        # reset bin parameters
                        start_sec = word_start_sec
                        start_microsec = word_start_microsec
                        end_sec = start_sec + bin_size
                        transcript = result.alternatives[0].words[i + 1].word

                        index += 1
                except IndexError:
                    pass
            # append transcript of last transcript in bin
            transcriptions.append(srt.Subtitle(index, datetime.timedelta(0, start_sec, start_microsec),
                                               datetime.timedelta(0, last_word_end_sec, last_word_end_microsec),
                                               transcript))
            index += 1
        except IndexError:
            pass

    # turn transcription list into subtitles
    subtitles = srt.compose(transcriptions)
    with open("{}.srt".format(subtitle_filename), "w") as f:
        f.write(subtitles)

    f.close()
    os.remove(tempAudioFilename)


"""
    After creating a subtitle file (.srt) this function can be used to add it to the video file.
    
    Place the video file in the same directory as this function.
    Give video_file parameter the video file name with the extension (.mp4)
    Give subtitle_file parameter the subtitle file name including the extension (.srt)
"""
def add_subtitle_to_video(video_file, subtitle_file):
    video_file_exists = os.path.exists(video_file)
    subtitle_file_exists = os.path.exists(subtitle_file)
    if (video_file_exists and subtitle_file_exists):
        print("adding subtitle: {} to video file: {} please wait...".format(subtitle_file, video_file))
        os.system("ffmpeg -y -i {} -vf subtitles={} {}".format(video_file, subtitle_file, "with_subtitles_" + video_file))
    else:
        if (not video_file_exists):
            print("video file: {} does not exist".format(video_file))
        if (not subtitle_file_exists):
            print("audio file: {} does not exist".format(subtitle_file))


"""
Here is an example of how the function call should be. 

1. Do generate_subtitles(..), to generate the subtitle file using google cloud speech to text api.
2. Do any modifications necessary to the subtitles file and then run add_subtitle_to_video(..) to add the 
subtitle to the video.

"""
# generate_subtitles("sample_target.mp4", "temp_subtitles")
# add_subtitle_to_video("sample_target.mp4", "temp_subtitles.srt")