#opensubtitles.org
#Subtitles service allowed by www.OpenSubtitles.org

OS_API = 'http://plexapp.api.opensubtitles.org/xml-rpc'
OS_LANGUAGE_CODES = 'http://www.opensubtitles.org/addons/export_languages.php'
OS_PLEX_USERAGENT = 'plexapp.com v9.0'
subtitleExt       = ['utf','utf8','utf-8','sub','srt','smi','rt','ssa','aqt','jss','ass','idx']

RE_IMDB_ID = Regex('^tt(\d+)$')
TVDB_SERIES_INFO = 'http://thetvdb.plexapp.com/data/series/%s'
 
def Start():
  HTTP.CacheTime = CACHE_1DAY
  HTTP.Headers['User-Agent'] = 'plexapp.com v9.0'

@expose
def GetImdbIdFromHash(openSubtitlesHash, lang):
  proxy = XMLRPC.Proxy(OS_API)
  try:
    os_movieInfo = proxy.CheckMovieHash('',[openSubtitlesHash])
  except:
    return None
    
  if os_movieInfo['data'][openSubtitlesHash] != []:
    return MetadataSearchResult(
      id    = "tt" + str(os_movieInfo['data'][openSubtitlesHash]['MovieImdbID']),
      name  = str(os_movieInfo['data'][openSubtitlesHash]['MovieName']),
      year  = int(os_movieInfo['data'][openSubtitlesHash]['MovieYear']),
      lang  = lang,
      score = 90)
  else:
    return None

def opensubtitlesProxy():
  proxy = XMLRPC.Proxy(OS_API)
  username = Prefs["username"]
  password = Prefs["password"]
  if username == None or password == None:
    username = ''
    password = ''
  token = proxy.LogIn(username, password, 'en', OS_PLEX_USERAGENT)['token']
  return (proxy, token)

def fetchSubtitles(proxy, token, part, imdbID=''):
  langList = [Prefs["langPref1"]]
  if Prefs["langPref2"] != 'None' and Prefs["langPref1"] != Prefs["langPref2"]:
    langList.append(Prefs["langPref2"])
  for l in langList:
    Log('Looking for match for GUID %s and size %d' % (part.openSubtitleHash, part.size))
    subtitleResponse = proxy.SearchSubtitles(token,[{'sublanguageid':l, 'moviehash':part.openSubtitleHash, 'moviebytesize':str(part.size)}])['data']
    #Log('hash/size search result: ')
    #Log(subtitleResponse)
    if subtitleResponse == False and imdbID != '': #let's try the imdbID, if we have one...
      subtitleResponse = proxy.SearchSubtitles(token,[{'sublanguageid':l, 'imdbid':imdbID}])['data']
      Log('Found nothing via hash, trying search with imdbid: ' + imdbID)
      #Log(subtitleResponse)
    if subtitleResponse != False:
      for st in subtitleResponse: #remove any subtitle formats we don't recognize
        if st['SubFormat'] not in subtitleExt:
          Log('Removing a subtitle of type: ' + st['SubFormat'])
          subtitleResponse.remove(st)
      st = sorted(subtitleResponse, key=lambda k: int(k['SubDownloadsCnt']), reverse=True)[0] #most downloaded subtitle file for current language
      if st['SubFormat'] in subtitleExt:
        subUrl = st['SubDownloadLink']
        subGz = HTTP.Request(subUrl, headers={'Accept-Encoding':'gzip'}).content
        subData = Archive.GzipDecompress(subGz)
        part.subtitles[Locale.Language.Match(st['SubLanguageID'])][subUrl] = Proxy.Media(subData, ext=st['SubFormat'])
    else:
      Log('No subtitles available for language ' + l)

def TvdbId_to_ImdbId(tvdb_id):
  try:
    xml = XML.ElementFromURL(TVDB_SERIES_INFO % tvdb_id)
    imdb_id = xml.xpath('/Data/Series/IMDB_ID')[0].text
  except:
    imdb_id = ''
  return imdb_id[2:] if RE_IMDB_ID.search(imdb_id) else ''

class OpenSubtitlesAgentMovies(Agent.Movies):
  name = 'OpenSubtitles.org'
  languages = [Locale.Language.NoLanguage]
  primary_provider = False
  #contributes_to = ['com.plexapp.agents.imdb']
  
  def search(self, results, media, lang):
    Log(media.primary_metadata.id)
    results.Append(MetadataSearchResult(
      id    = media.primary_metadata.id,
      score = 100
    ))
    
  def update(self, metadata, media, lang):
    (proxy, token) = opensubtitlesProxy()
    imdb_id = metadata.id[2:] if RE_IMDB_ID.search(metadata.id) else ''
    for i in media.items:
      for part in i.parts:
        fetchSubtitles(proxy, token, part, imdb_id)

class OpenSubtitlesAgentTV(Agent.TV_Shows):
  name = 'OpenSubtitles.org'
  languages = [Locale.Language.NoLanguage]
  primary_provider = False
  #contributes_to = ['com.plexapp.agents.thetvdb']

  def search(self, results, media, lang):
    results.Append(MetadataSearchResult(
      id    = media.primary_metadata.id,
      score = 100
    ))

  def update(self, metadata, media, lang):
    (proxy, token) = opensubtitlesProxy()
    imdb_id = TvdbId_to_ImdbId(metadata.id)
    for s in media.seasons:
      # just like in the Local Media Agent, if we have a date-based season skip for now.
      if int(s) < 1900:
        for e in media.seasons[s].episodes:
          for i in media.seasons[s].episodes[e].items:
            for part in i.parts:
              fetchSubtitles(proxy, token, part, imdb_id)
