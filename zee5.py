import xmltodict, codecs, shutil, subprocess, os, argparse, json, time, binascii, base64, requests, sys, ffmpy, re, titlecase, unidecode, itertools, isodate
from collections import OrderedDict
import pycaption
from pycaption import SRTWriter, WebVTTReader
from pycaption.exceptions import CaptionReadNoCaptions
from pymediainfo import MediaInfo
from pywidevine.decrypt.wvdecrypt import WvDecrypt
import pywidevine.namehelper as namer
import uuid

config = {
    'cloudfront': "https://mediacloudfront.zee5.com",
    'akamai': "https://zee5vod.akamaized.net",
    'tata': "https://mediatata.zee5.com"
}
script_name = "ZEE5 Ripper"
script_ver = "3.0"

parser = argparse.ArgumentParser(description=f">>> {script_name} {script_ver} <<<")
parser.add_argument('-id', action="store", dest='zee5_id', help="Add Zee5 id or url")
parser.add_argument("-s", dest="season", action="store", help="Rip Full season.")
parser.add_argument("-e", action="store", dest='episode', help="add episode.", default=0)
parser.add_argument('-q', action="store", dest='customquality', help="For configure quality of video.", default=0)
parser.add_argument("--uhd", dest="uhd", help="Use for downloading 4K and hevc videos", action="store_true")
parser.add_argument("--high", dest="high", help="Use for High profile videos downloading", action="store_true")
parser.add_argument("--license", dest="license", help="If set, print all profiles keys and exit.", action="store_true")
parser.add_argument("--nv", "--no-video", dest="novideo", help="If set, don't download video", action="store_true")
parser.add_argument("--na", "--no-audio", dest="noaudio", help="If set, don't download audio", action="store_true")
parser.add_argument("--ns", "--no-subs", dest="nosubs", help="If set, don't download subs", action="store_true")
parser.add_argument("--subs", dest="subs_only", help="If set, only download subs", action="store_true")
parser.add_argument("--keep", dest="keep", help="If set, well keep all files after mux, by default all erased.", action="store_true")
args = parser.parse_args()

currentFile = __file__
realPath = os.path.realpath(currentFile)
dirPath = os.path.dirname(realPath)
dirName = os.path.basename(dirPath)
ytdlexe = dirPath + "/binaries/yt-dlp.exe"
aria2cexe = dirPath + "/binaries/aria2c.exe"
ffmpegpath = dirPath + "/binaries/ffmpeg.exe"
mp4decryptexe = dirPath + "/binaries/mp4decrypt.exe"
mkvmergepath = dirPath + "/binaries/mkvmerge.exe"
tokenfile = dirPath + "/token.json"
out = dirPath + "/Downloads"
confi = dirPath + "/config.json"

proxies = {'https': 'http://170.187.249.161:3535/'}

def token():
    if os.path.isfile(tokenfile):
        with open(tokenfile, 'r') as f:
            return json.load(f)
    else:
        if os.path.isfile(confi):
            with open("config.json") as json_data:
                login = json.load(json_data)
                email = login[0]['email']
                password = login[0]['password']
                headers = {'user-agent': ua(), 'Content-Type': 'application/json'}
                data = {"email": email, "password": password,"aid":"91955485578","lotame_cookie_id":"","guest_token":"iuGMwSMz0HdoCQ3jrLP1000000000000","platform":"app","version":"2.51.37"}
                token = requests.post('https://whapi.zee5.com/v1/user/loginemail_v2.php', data=json.dumps(data), headers=headers, proxies=proxies).json()['access_token']
                with open(tokenfile, 'w') as f:
                    f.write(json.dumps(token, indent=4))

def session():
    session_token = requests.get("https://useraction.zee5.com/token/platform_tokens.php?platform_name=androidtv_app", proxies=proxies).json()["token"]
    return {'x-access-token': session_token}

dolly = session()['x-access-token']
atho = f'bearer {token()}'

def download_subs(url, name):
    if os.path.exists(name):
        return
    print("\nDownloading subtitle: {}".format(os.path.basename(name)))
    suburl = url.replace('cenc_dash', 'hls')
    subprocess.run([ffmpegpath, '-y', '-hide_banner', '-loglevel', 'warning', '-i', url, name])
    time.sleep (50.0/1000.0)
    return

def FixSeq(seq):
    if int(len(str(seq))) == 1:
        return f'0{str(seq)}'

    return str(seq)

def ReplaceDontLikeWord(X):
    try:    
        X = X.replace(" : ", " - ").replace(": ", " - ").replace(":", " - ").replace("&", "and").replace("+", "").replace(";", "").replace("ÃƒÂ³", "o").\
            replace("[", "").replace("'", "").replace("]", "").replace("/", "-").replace("//", "").\
            replace("’", "'").replace("*", "x").replace("<", "").replace(">", "").replace("|", "").\
            replace("~", "").replace("#", "").replace("%", "").replace("{", "").replace("}", "").replace(",","").\
            replace("?","").encode('latin-1').decode('latin-1')
    except Exception:
        X = X.decode('utf-8').replace(" : ", " - ").replace(": ", " - ").replace(":", " - ").replace("&", "and").replace("+", "").replace(";", "").\
            replace("ÃƒÂ³", "o").replace("[", "").replace("'", "").replace("]", "").replace("/", "").\
            replace("//", "").replace("’", "'").replace("*", "x").replace("<", "").replace(">", "").replace(",","").\
            replace("|", "").replace("~", "").replace("#", "").replace("%", "").replace("{", "").replace("}", "").\
            replace("?","").encode('latin-1').decode('latin-1')
    
    return titlecase.titlecase(X)

def convert_size(size_bytes):
    if size_bytes == 0:
        return '0bps'
    else:
        s = round(size_bytes / 1000, 0)
        return '%ikbps' % s

def get_size(size):
    power = 1024
    n = 0
    Dic_powerN = {0:'',  1:'K',  2:'M',  3:'G',  4:'T'}
    while size > power:
        size /= power
        n += 1
    return str(round(size, 2)) + Dic_powerN[n] + 'B'

def single(id):
    PLAYBACK_URL = "https://spapi.zee5.com/singlePlayback/getDetails/secure"
    headers = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36"
    }
    data = {
    'Authorization': atho,
    'x-access-token': dolly
    }
    params = {
    'content_id': id,
    'device_id': 'iuGMwSMz0HdoCQ3jrLP1000000000000',
    'platform_name': 'androidtv_app',
    'translation': 'en',
    'user_language': 'en,hi,ta,pa',
    'country': 'IN',
    'state': 'DL',
    'app_version': '2.50.79',
    'user_type': 'premium',
    'check_parental_control': False,
    'uid': '90087e8f-9eb1-4c0e-a6ef-0686279409f2',
    'ppid': 'iuGMwSMz0HdoCQ3jrLP1000000000000',
    'version': 12
    }
    resp = requests.post(PLAYBACK_URL, headers=headers, params=params, json=data, proxies=proxies).json()
    title = resp['assetDetails']['title']
    
    if args.uhd:
        try:
            deer = resp['assetDetails']['video_url']['4k_mpd']
        except:
            deer = resp['assetDetails']['video_url']['mpd']
    else:
        deer = resp['assetDetails']['video_url']['mpd']

    if args.high:
        deer = resp['assetDetails']['video_url']['mpd']
    drmdata = resp['keyOsDetails']['sdrm']
    nl = resp['keyOsDetails']['nl']

    subs = []
    subtitles = resp['assetDetails']['subtitle_url']
    if len(subtitles) != 0:
        for sub in subtitles:
            subs.append(
                {
                'url': sub['url'],
                'lang': sub['language']
                }
            )
    else: subs = None

    return deer, title, subs, drmdata, nl

def getseries(seriesID):
    playlist = []
    api = 'https://gwapi.zee5.com/content/tvshow/'
    series_params = {
        'translation': 'en',
        'country': country()
    }
    SeasonNo = str(args.season)
    if not args.season:
        SeasonNo = str(input("\nEnter Season Number: "))
    res = requests.get(api+seriesID, params=series_params, headers={'x-access-token': session()}, proxies=proxies).json()
    seriesname = res.get('title')
    for season in res.get('seasons'):
        if int(SeasonNo) == int(season.get('index')):
            seasonID = season.get('id')
    
    for num in itertools.count(1):
        season_params = {
            'season_id': seasonID,
            'translation': 'en',
            'country': country(),	
            'type': 'episode',
            'on_air': 'true',
            'asset_subtype': 'tvshow',
            'page': num,
            'limit': 25
        }		
        res = requests.get(api, params=season_params, headers=session(), proxies=proxies).json()
        if res.get('error_msg'):
            print(res)
            sys.exit()	
        episodesCount = res.get('total_episodes')
        for item in res.get('episode'):
            episodeNo = item.get('episode_number')
            episodeID = item.get('id')
            seasonNo = season.get('index')
            try:
                playlist.append({
                    'id': episodeID,
                    'number': episodeNo,
                    'name': seriesname + ' ' + 'S{}E{}'.format(FixSeq(seasonNo), FixSeq(episodeNo))
                })
            except Exception:
                continue

        if not res.get('next_episode_api'):
            break
    
    return playlist

def parsempd(url):
    audioslist = []
    videoslist = []
    subtitlelist = []
    mpd = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36'}, proxies=proxies).text
    if mpd:
        mpd = re.sub(r"<!--  -->","",mpd)
        mpd = re.sub(r"<!-- Created+(..*)","",mpd)		
        mpd = re.sub(r"<!-- Generated+(..*)","",mpd)
    mpd = json.loads(json.dumps(xmltodict.parse(mpd)))
    length = isodate.parse_duration(mpd['MPD']['@mediaPresentationDuration']).total_seconds()

    AdaptationSet = mpd['MPD']['Period']['AdaptationSet']
    baseurl = url.rsplit('manifest')[0]

    for ad in AdaptationSet:
        if ad['@mimeType'] == "audio/mp4":
            if ad.get('ContentProtection') is not None:
                for y in ad.get('ContentProtection'):
                    if y.get('@schemeIdUri') == 'urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed':
                        pssh = y.get('cenc:pssh')
    for ad in AdaptationSet:
        if ad['@mimeType'] == "audio/mp4":
            try:
                auddict = {
                'id': ad['Representation']['@id'],
                'codec': ad['Representation']['@codecs'],
                'bandwidth': ad['Representation']['@bandwidth'],
                'lang': ad['@lang']
                }
                audioslist.append(auddict)
            except Exception:
                for item in ad['Representation']:
                    auddict = {
                    'id': item['@id'],
                    'codec': item['@codecs'],
                    'bandwidth': item['@bandwidth'],
                    'lang': ad['@lang']
                    }
                    audioslist.append(auddict)

    for ad in AdaptationSet:
        if ad['@mimeType'] == "video/mp4":
            for item in ad['Representation']:
                viddict = {
                'width': item['@width'],
                'height': item['@height'],
                'id': item['@id'],
                'codec': item['@codecs'],
                'bandwidth': item['@bandwidth']
                }
                videoslist.append(viddict)

    for ad in AdaptationSet:
        if ad['@mimeType'] == "text/vtt":
            subdict = {
            'id': ad['Representation']['@id'],
            'lang': ad['@lang'],
            'bandwidth': ad['Representation']['@bandwidth'],
            'url': baseurl + ad['Representation']['BaseURL']
            }
            subtitlelist.append(subdict)

    videoslist = sorted(videoslist, key=lambda k: int(k['bandwidth']))
    audioslist = sorted(audioslist, key=lambda k: int(k['bandwidth']))

    return videoslist, audioslist, subtitlelist, baseurl, pssh, length

def searchinlist(yourlist, search):
    videoslist = []

    for item in yourlist:
        if int(item['height']) == int(search):
            viddict = {
            'width': item['width'],
            'height': item['height'],
            'id': item['id'],
            'codec': item['codec'],
            'bandwidth': item['bandwidth']}
            videoslist.append(viddict)

    videoslist = sorted(videoslist, key=lambda k: int(k['bandwidth']))

    return videoslist

def ismdash(streamid, filename, mpdurl, baseurl):
    txturls = filename + 'links.txt'
    json_file = 'json.info.json'
    mpd = requests.get(url, proxies=proxies)
    if 'prime' in mpdurl:
        subprocess.run([ytdlexe, '--allow-unplayable-formats', '-k', '--quiet', '--no-warnings', '--user-agent', 'Mozilla/5.0 (iPhone; CPU iPhone OS 13_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/83.0.4103.61 Mobile/15E148 Safari/604.1', '-f', streamid, '--fixup', 'never', '--proxy', 'http://170.187.249.161:3535/', mpdurl, '-o', filename, '--external-downloader',aria2cexe, '--external-downloader-args', '-x 16 -s 16 -k 1M'])
        time.sleep(1)

        return

    ytdl_command = [
                    'yt-dlp',
                    '--allow-unplayable-formats',
                    '--no-check-certificate',
                    '--no-warnings',
                    '--quiet',
                    '--write-info-json',
                    '--skip-download',
                    '-o', 'json',
                    mpdurl
    ]

    subprocess.call(ytdl_command, stdout=open(os.devnull, 'wb'))
    time.sleep (50.0/1000.0)

    with open(json_file) as json_data:  
        data = json.load(json_data)

    os.remove(json_file)

    manifestformats = data['formats']

    fragmentslist = []
    fragmentnames = []

    for item in manifestformats:
        if item['format_id'] == streamid:
            for frag in item['fragments']:
                fragmentslist.append(baseurl+frag['path'])
                fragmentnames.append(frag['path'].split('/')[-1])

    with open(txturls, 'w') as fd:
        fd.write('\n'.join(fragmentslist) + '\n')

    time.sleep (50.0/1000.0)

    download = subprocess.Popen(
        [aria2cexe, 
        f'--input-file={txturls}',
        '-x16', '-j16', '-s16',
        '--retry-wait=3',
        '--max-tries=0', 
        '--console-log-level=error', 
        '--download-result=hide',
        '--allow-overwrite=true',
        ])
    download.wait()

    time.sleep (50.0/1000.0)

    output = open(filename ,"wb")
    for fragment in fragmentnames:
        fragment = os.path.join(out, fragment)
        if os.path.isfile(fragment):
            shutil.copyfileobj(open(fragment,"rb"),output)
            os.remove(fragment)
    output.close()

    os.remove(txturls)
    
    return

def do_decrypt(pssh, drmdata, nl):
    wvdecrypt = WvDecrypt(pssh)
    chal = wvdecrypt.get_challenge()
    headers = {
                'origin': 'https://www.zee5.com',
                'referer': 'https://www.zee5.com/',
                'customdata': drmdata,
                'nl': nl,                
                }
    resp = requests.post('https://spapi.zee5.com/widevine/getLicense', data=chal, headers=headers, proxies=proxies)
    lic = resp.content
    license_b64 = base64.b64encode(lic).decode('utf-8') 
    wvdecrypt.update_license(license_b64)
    keys = wvdecrypt.start_process()

    return keys

def keysOnly(keys):
    for key in keys:
        if key.type == 'CONTENT':
            key = ('{}:{}'.format(key.kid.hex(), key.key.hex()))

    return key

def proper(keys):
    commandline = [mp4decryptexe]
    for key in keys:
        if key.type == 'CONTENT':
            commandline.append('--key')
            commandline.append('{}:{}'.format(key.kid.hex(), key.key.hex()))

    return commandline

def decrypt(keys_, inputt, output):
    Commmand = proper(keys_)
    Commmand.append(inputt)
    Commmand.append(output)

    wvdecrypt_process = subprocess.Popen(Commmand)
    stdoutdata, stderrdata = wvdecrypt_process.communicate()
    wvdecrypt_process.wait()

    return

def do_clean(CurrentName):
    try:    
        os.system('if exist "' + CurrentName + '*.mp4" (del /q /f "' + CurrentName + '*.mp4")')
        os.system('if exist "' + CurrentName + '*.h265" (del /q /f "' + CurrentName + '*.h265")')
        os.system('if exist "' + CurrentName + '*.h264" (del /q /f "' + CurrentName + '*.h264")')
        os.system('if exist "' + CurrentName + '*.eac3" (del /q /f "' + CurrentName + '*.eac3")')
        os.system('if exist "' + CurrentName + '*.m4a" (del /q /f "' + CurrentName + '*.m4a")')
        os.system('if exist "' + CurrentName + '*.ac3" (del /q /f "' + CurrentName + '*.ac3")')
        os.system('if exist "' + CurrentName + '*.srt" (del /q /f "' + CurrentName + '*.srt")')
        os.system('if exist "' + CurrentName + '*.vtt" (del /q /f "' + CurrentName + '*.vtt")')
        os.system('if exist "' + CurrentName + '*.txt" (del /q /f "' + CurrentName + '*.txt")')
        os.system('if exist "' + CurrentName + '*.aac" (del /q /f "' + CurrentName + '*.aac")')
        os.system('if exist "' + CurrentName + '*.m3u8" (del /q /f "' + CurrentName + '*.m3u8")')
    except Exception:
        pass

    return 

def demux(inputName, outputName):
    ff = ffmpy.FFmpeg(
        executable=ffmpegpath,
        inputs={inputName: None},
        outputs={outputName: '-c copy'},
        global_options="-y -hide_banner -loglevel warning"
    )

    ff.run()
    time.sleep (50.0/1000.0)
    
    return True

def Downloader(manifest, subtitles, output, drmdata, nl):

    print('\nRipping: {}'.format(output))
    
    print('\nParsing MPD...')
    videoslist, audioslist, subslist, baseurl, pssh, length = parsempd(manifest)
    print('Done!')

    if subtitles is None:
        subtitles = subslist
    
    try:
        print("\nVIDEO LIST")
        for z in videoslist:
            print('VIDEO' + ' | Codec: ' + z['codec'] + ' | Bandwidth: ' + convert_size(int(z['bandwidth'])) + ' | Resolution: ' + z['width'] + 'x' + z['height'] + ' | Size: ' + get_size(length * float(z['bandwidth']) * 0.125))
        print("\nAUDIO LIST")
        for z in audioslist:
            print('AUDIO' + ' | Lang: ' + z['lang'] + ' | Codec: ' + z['codec'] + ' | bandwidth: ' + convert_size(int(z['bandwidth'])) + ' | Size: ' + get_size(length * float(z['bandwidth']) * 0.125))
        print("\nSUBS LIST")
        if subtitles is None:
            print('None')
        else:
            for z in subtitles:
                print('SUB' + ' | Lang: ' + z['lang'] + ' | Type: ' + 'WEBVTT')

    except Exception:
        pass

    quality_available = [int(x['height']) for x in videoslist]
    quality_available = list(OrderedDict.fromkeys(quality_available))

    if quality == 'Max':
        video = videoslist[-1]
    else:
        quality_available = [int(x['height']) for x in videoslist]
        quality_available = list(OrderedDict.fromkeys(quality_available))
        if not int(quality) in quality_available:
            print(f'This quality is not available, the available ones are: ' + ', '.join(str(x) for x in quality_available) + '.')
            height = input('Enter a correct quality (without p): ').strip()
        else:
            height = quality

        video = searchinlist(videoslist, height)
        video = video[-1]

    audioList2 = []
    AddedAudios = set()
    for aud in reversed(audioslist): #reversed
        if aud['lang'] not in AddedAudios:
            audioList2.append(aud)
            AddedAudios.add(aud['lang'])
    audioslist = sorted(audioList2, key=(lambda k: int(k['bandwidth'])))
    
    #audioslist = audioslist[-1]
    if args.novideo and args.noaudio and not args.license:
        pass	
    
    else:
        if not args.subs_only:
            KEYS = do_decrypt(pssh, drmdata, nl)
            print('\nKEY: ' + keysOnly(KEYS) + '\n')
            if args.license:
                return

    name = os.path.join(out, output)
    VideoEncrypted = name + '_' + video['height'] + '_encrypted_video' + '.mp4'
    VideoDecrypted = name + '_' + video['height'] + '_decrypted_video' + '.mp4'
    VideoDemuxed = name + '_' + video['height'] + '_demuxed_video' + '.mp4'
    AudioEncrypted = name + '_{lang}' + '_encrypted_audio' + '.m4a'
    AudioDecrypted = name + '_{lang}' + '_decrypted_audio' + '.m4a'
    srtname = name + '_{lang}' + '.srt'
    mkvname = name + '.mkv'
    
    if not subtitles is None:
        for sub in subtitles:
            download_subs(sub['url'], srtname.format(lang=sub['lang']))
            print('Done!')

    if args.subs_only:
        return
    
    # V2-PRIME STUFF BY SKR (Telegram @SKR1405)
    #########################################################################################################################
    if 'v2-prime.akamaized.net' in manifest:
        from urllib.parse import urljoin
        from itertools import zip_longest
        ids = [video['id']] + [aud['id'] for aud in audioslist]

        json_info = subprocess.check_output([
                    'yt-dlp',
                    '--allow-unplayable-formats',
                    '--no-check-certificate',
                    '--no-warnings',
                    '--quiet',
                    '--skip-download',
                    '--dump-json',
                    manifest])
        user_agent = json.loads(json_info)['formats'][0]['http_headers']['User-Agent']
        fragments_to_download = []
        for format in json.loads(json_info)['formats']:
            if format['format_id'] in ids:
                for index, fragment in enumerate(format['fragments'], 1):
                    fragment['path'] = urljoin(format['fragment_base_url'], fragment['path'])
                    fragment['output'] = f'{format["format_id"]}.{index}'
                fragments_to_download.append(format['fragments'])
        o_fragments_to_download = fragments_to_download
        fragments_to_download = [fragment for sublist in zip_longest(*fragments_to_download, fillvalue=None) for fragment in sublist if fragment != None]
        urls_file_path = os.path.join(out, 'v2-prime.urls')
        with open(urls_file_path, 'w') as urls_file:
            for fragment in fragments_to_download:
                urls_file.write(fragment['path'])
                urls_file.write('\n\t')
                urls_file.write(f'out={fragment["output"]}')
                urls_file.write('\n')
        download = subprocess.Popen(
            [aria2cexe, 
            f'--input-file={urls_file_path}',
            f"--user-agent={user_agent}",
            '-x16', '-j16', '-s16',
            '--retry-wait=3',
            '--max-tries=0', 
            '--console-log-level=error', 
            '--download-result=hide',
            '--allow-overwrite=true'
            ])
        download.wait()
        os.remove(urls_file_path)

        for fragments in o_fragments_to_download:
            if fragments[0]['output'].split('.')[0] == video['id']:
                with open(VideoEncrypted ,"wb") as output:
                    for fragment in fragments:
                        fragment = os.path.join(out, fragment['output'])
                        if os.path.isfile(fragment):
                            shutil.copyfileobj(open(fragment,"rb"),output)
                            os.remove(fragment)
            else:
                for aud in audioslist:
                    if fragments[0]['output'].split('.')[0] == aud['id']:
                        AudEnc = AudioEncrypted.format(lang=aud['lang'])
                        with open(AudEnc ,"wb") as output:
                            for fragment in fragments:
                                fragment = os.path.join(out, fragment['output'])
                                if os.path.isfile(fragment):
                                    shutil.copyfileobj(open(fragment,"rb"),output)
                                    os.remove(fragment)
    #########################################################################################################################
      


    if not args.novideo:
        if not os.path.isfile(VideoEncrypted) and not os.path.isfile(VideoDecrypted) and not os.path.isfile(VideoDemuxed):
            print('\nDownloading Video...')
            downloadvideo = ismdash(video['id'].replace('/', '_'), VideoEncrypted, url, baseurl)

        if os.path.isfile(VideoEncrypted) and not os.path.isfile(VideoDecrypted) and not os.path.isfile(VideoDemuxed):
            #print()
            print('\nDecrypting Video...')
            decryptvideo = decrypt(KEYS, VideoEncrypted, VideoDecrypted)
            print('Done!')

        if os.path.isfile(VideoDecrypted) and not os.path.isfile(VideoDemuxed):
            if 'avc' in video['codec']:
                print('\nRemuxing Video...')
                remuxvideo = demux(VideoDecrypted, VideoDemuxed)
                print('Done!')
            else:
                VideoDemuxed = VideoDecrypted

    if not args.noaudio:	
        for aud in audioslist:
            AudEnc = AudioEncrypted.format(lang=aud['lang'])
            AudDec = AudioDecrypted.format(lang=aud['lang'])

            if not os.path.isfile(AudEnc) and not os.path.isfile(AudDec):
                print('\nDownloading {} Audio...'.format(aud['lang']))
                downloadaudio = ismdash(aud['id'], AudEnc, url, baseurl)
                print('Done!')

            if os.path.isfile(AudEnc) and not os.path.isfile(AudDec):
                print('\nDecrypting {} Audio...'.format(aud['lang']))
                decryptaudio = decrypt(KEYS, AudEnc, AudDec)
                print('Done!')
            if os.path.isfile(AudDec):
                media_info = MediaInfo.parse(AudDec)
                for track in media_info.tracks:
                    if track.track_type == 'Audio':
                        if track.format == "E-AC-3":
                            AudioDemuxed = name + '_{lang}' + '_demuxed_audio' + '.eac3'
                        elif track.format == "AC-3":
                            AudioDemuxed = name + '_{lang}' + '_demuxed_audio' + '.eac3'
                        elif track.format == "AAC":
                            AudioDemuxed = name + '_{lang}' + '_demuxed_audio' + '.aac'

            AudDemux = AudioDemuxed.format(lang=aud['lang'])

            if os.path.isfile(AudDec) and not os.path.isfile(AudDemux):
                print('\nDemuxing {} Audio...'.format(aud['lang']))
                demuxaudio = demux(AudDec, AudDemux)
                print('Done!')
        
    if not args.novideo and not args.noaudio:
        mkvmerge_command = [mkvmergepath]
        mkvmerge_command.append('-o')
        mkvmerge_command.append('-q')		
        mkvmerge_command.append(mkvname)
        mkvmerge_command.append('--forced-track')
        mkvmerge_command.append('0:no')
        mkvmerge_command.append('--no-global-tags')
        mkvmerge_command.append('--no-chapters')
        mkvmerge_command.append(VideoDemuxed)

        for aud in audioslist:
            name = AudioDemuxed.format(lang=aud['lang'])
            if os.path.isfile(name):
                mkvmerge_command.append('--aac-is-sbr')
                mkvmerge_command.append('0:1')
                mkvmerge_command.append('--language')
                mkvmerge_command.append('0:{}'.format(aud['lang']))
                mkvmerge_command.append(name)

        if not subtitles is None:
            for sub in subtitles:
                subname = srtname.format(lang=sub['lang'])
                if os.path.isfile(subname):
                    mkvmerge_command.append('--sub-charset')
                    mkvmerge_command.append('0:UTF-8')			
                    mkvmerge_command.append('--language')
                    mkvmerge_command.append('0:{}'.format(sub['lang']))
                    mkvmerge_command.append('--forced-track')
                    mkvmerge_command.append('0:no')
                    mkvmerge_command.append('--default-track')
                    mkvmerge_command.append('0:no')
                    mkvmerge_command.append(subname)

        if not os.path.isfile(mkvname):
            print('\nMuxing Video and Audio...')
            mkvmerge_process = subprocess.Popen(mkvmerge_command)
            stdoutdata, stderrdata = mkvmerge_process.communicate()
            mkvmerge_process.wait()
            print('Done!')

    namer.rename(
        file=mkvname,
        source="ZEE5",
        group='Monkey-D-Luffy'
    )

    if args.keep:
        pass
    else:
        print('\nCleaning Directory...')
        do_clean(output)
        print('Done!')

    return

if __name__ == '__main__':
    
    if args.customquality: quality = args.customquality
    else: quality = 'Max'

    folders = [out]
    for f in folders:
        if not os.path.exists(f):
            os.makedirs(f)
        os.chdir(f)

    l = "\n__________________________\n"

    print(
        f"\n--  {script_name}  --{l}\n--  VERSION: {script_ver}  --{l}"
        )

    if args.zee5_id:
        link = str(args.zee5_id)
    else:
        link = str(input("\nEnter Zee5 ID or URL: "))

    if "https://" in link:
        zee5_id = link.split('/')[6]
    else:
        zee5_id = link

    if args.episode:
        episode = args.episode
        episodes = []
        IDs = getseries(zee5_id)
        for eps in IDs:
            if "~" in episode:
                if int(eps.get('number')) >= int(episode.replace('~', '')):
                    episodes.append({'id': eps.get('id'), 'name': eps.get('name'), 'number': eps.get('number')}) 
            elif str(episode).__contains__("-"):
                episode_range = episode.split("-")
                if int(episode_range[0]) <= int(eps.get('number')) <= int(episode_range[1]):
                    episodes.append({'id': eps.get('id'), 'name': eps.get('name'), 'number': eps.get('number')}) 
            elif str(episode).__contains__(","):
                for selected_episode in episode.split(","):
                    if int(selected_episode) == int(eps.get('number')):
                        episodes.append({'id': eps.get('id'), 'name': eps.get('name'), 'number': eps.get('number')}) 
            elif not str(episode).__contains__("-") and not str(episode).__contains__(","):
                if int(eps.get('number')) == int(episode):
                    episodes.append({'id': eps.get('id'), 'name': eps.get('name'), 'number': eps.get('number')})
        for x in sorted(episodes, key=lambda k: int(k["number"])):
            url, title, subtitles, drmdata, nl = single(str(x['id']))
            output = ReplaceDontLikeWord(unidecode.unidecode(x['name'])) + '-' + title
            episid = str(x['id'])
            Downloader(url, subtitles, output, drmdata, nl) 
        
        if not args.episode:
            IDs, se_name = series(series_id)
            for x in sorted(episodes, key=lambda k: int(k["number"])):
                url, title, subtitles, drmdata, nl = single(str(x['id']))
                output = ReplaceDontLikeWord(unidecode.unidecode(x['name'])) + '-' + title
                episid = str(x['id'])
                Downloader(url, subtitles, output, drmdata, nl)    
    else:
        url, output, subtitles, drmdata, nl = single(zee5_id) 
        Downloader(url, subtitles, ReplaceDontLikeWord(unidecode.unidecode(output)), drmdata, nl)
