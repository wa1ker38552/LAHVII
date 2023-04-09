import speech_recognition as sr
from twilio.rest import Client
from pygame import mixer
import webbrowser
import websockets
import subprocess
import requests
import pyaudio
import asyncio
import twilio
import json
import time
import gtts
import sys
import os

DEEPGRAM_API_KEY = ""
token = ''
account_sid = ''
auth_token = ''

model = 'text-davinci-003'
command_key = 'hey'
incoming_command = False

system = 'Give all your following responses as simply as possible while still providing a sufficient answer to the question'
error = "Sorry I didn't understand that!"
x = 0

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 8000

client = Client(account_sid, auth_token)
audio_queue = asyncio.Queue()

def replace_numbers(i):
    i = i.replace('one', '1')
    i = i.replace('two', '2')
    i = i.replace('three', '3')
    i = i.replace('four', '4')
    i = i.replace('five', '5')
    i = i.replace('six', '6')
    i = i.replace('seven', '7')
    i = i.replace('eight', '8')
    i = i.replace('nine', '9')
    i = i.replace('zero', '0')
    return i.replace(' ', '')


def speak(text):
    global x
    print('Speaking')

    tts = gtts.gTTS(text)
    tts.save(f'rec/{x}.mp3')
    mixer.init()
    mixer.music.load(f'rec/{x}.mp3')
    mixer.music.play()
    while mixer.music.get_busy(): continue
    x += 1

def get_applications():
    cmd = 'powershell "gps | where {$_.MainWindowTitle } | select Description'
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    lines = []
    for line in proc.stdout:
        if line.rstrip():
            lines.append(line.decode().rstrip())
    return lines[3:]

def send_text(target, message):
    client.messages.create(body=message, to=target, from_='+18449612533')

def completions(p):
    global system, token, model
    request = requests.post('https://api.openai.com/v1/completions',
                            headers={'Accept': 'application/json', 'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
                            json={"model": model, 'prompt': p})

    # return request.json()['choices'][0]['message']['content']
    return request.json()['choices'][0]['text']

def callback(input_data, frame_count, time_info, status_flags):
    audio_queue.put_nowait(input_data)
    return (input_data, pyaudio.paContinue)

async def microphone():
    audio = pyaudio.PyAudio()
    stream = audio.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK,
        stream_callback=callback
    )
    stream.start_stream()

    while stream.is_active():
        await asyncio.sleep(0.1)

    # stream.stop_stream()
    # stream.close()

async def sender(ws):
    try:
        while True:
            data = await audio_queue.get()
            await ws.send(data)
    except Exception as e: pass

async def receiver(ws):
    global incoming_command, command_key, x
    async for msg in ws:
        msg = json.loads(msg)
        try:
            transcript = msg['channel']['alternatives'][0]['transcript']
        except KeyError:
            transcript = ''

        if transcript:
            if incoming_command:
                if 'applications' in transcript.lower() and 'open' in transcript.lower():
                    apps = get_applications()
                    speak('and '.join(apps)+' are open right now')

                elif 'save contact' in transcript.lower():
                    number = replace_numbers(' '.join(transcript.lower().split()[2:-2]))
                    name = transcript.lower().split()[-1]

                    data = json.loads(open('contacts.json', 'r').read())
                    if not name in data:
                        data[name] = number
                        with open('contacts.json', 'w') as file:
                            file.write(json.dumps(data, indent=2))
                        speak(f'Saved the contact {name} as {number}')
                    else:
                        speak(f'{name} is already saved in contacts')

                elif 'delete contact' in transcript.lower():
                    data = json.loads(open('contacts.json', 'r').read())
                    name = transcript.lower().split()[-1]
                    if name in data:
                        del data[name]
                        with open('contacts.json', 'w') as file:
                            file.write(json.dumps(data, indent=2))
                        speak(f'Deleted the contact {name}')
                    else:
                        speak(f'{name} isnt saved in contacts')

                elif 'text' in transcript.lower():
                    target = transcript.lower().split("text")[-1][1:]
                    data = json.loads(open('contacts.json', 'r').read())
                    if target in data:
                        name = target
                        target = data[target]
                        speak(f'What message do you want to send to {name}?')
                    else:
                        speak(f'What message do you want to send to {target}?')
                    print('Listening for message...')

                    rec = sr.Recognizer()
                    with sr.Microphone() as source:
                        audio = rec.record(source, duration=3)
                        text = rec.recognize_google(audio, language='en-IN', show_all=True)
                    target = replace_numbers(target)

                    try:
                        send_text('+1'+target, text['alternative'][0]['transcript'])
                        speak(f"Sent the message {text['alternative'][0]['transcript']} to {target}")
                    except twilio.base.exceptions.TwilioRestException:
                        speak(f"There was an error with the phone number {target}")
                    except KeyError:
                        speak("Sorry I didn't understand that, try using the command again")
                    except TypeError:
                        speak("Sorry I didn't understand that, try using the command again")
                    incoming_command = False
                    os.startfile(sys.argv[0])
                    sys.exit()

                elif 'show' in transcript.lower() and 'images' in transcript.lower():
                    query = ' '.join(transcript.lower().split()[transcript.lower().split().index('of')+1:])
                    webbrowser.get().open(f'https://www.google.com/search?q={query}&source=lnms&tbm=isch&sa=X&ved=2ahUKEwjN5NWMz5v-AhUgADQIHeYPCAIQ0pQJegQIBRAC&biw=1517&bih=690&dpr=0.9')
                    speak(f'Showing images of {query}')

                elif 'search' in transcript.lower():
                    webbrowser.get().open(f'https://google.com/search?q='+transcript.lower().replace('search', '').replace('for', ''))
                    speak('Finished searching')

                elif 'open' in transcript.lower() and 'website' in transcript.lower():
                    webbrowser.get().open(f'https://{transcript.lower().split()[-1]}.com')
                    speak('Finished opening website')
                else:
                    print('Querying GPT')
                    c = completions(transcript)
                    speak(c)
                    print('finished speaking')

                incoming_command = False
            else:
                if command_key in transcript.lower():
                    incoming_command = True
                    print('Listening to command...')
                    mixer.init()
                    mixer.music.load(f'chime.mp3')
                    mixer.music.play()
                    while mixer.music.get_busy(): continue

async def process():
    extra_headers = {'Authorization': 'token '+DEEPGRAM_API_KEY}
    async with websockets.connect('wss://api.deepgram.com/v1/listen?encoding=linear16&sample_rate=16000&channels=1', extra_headers=extra_headers) as ws:
        await asyncio.gather(sender(ws), receiver(ws))

async def run():
    await asyncio.gather(microphone(), process())

if __name__ == '__main__':
    # 650 898 3822
    asyncio.run(run())
