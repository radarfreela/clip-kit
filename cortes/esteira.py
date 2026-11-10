# Esteira de cortes de GTA 6 .
# 
# corta qualquer JOGO (nunca Just Chatting/conversa, nunca RP, nunca GTA V); quando houver GTA 6, ele vem sempre primeiro.
# A cada rodada: olha as lives gravadas (VOD) dos canais da Twitch → só lives JÁ ENCERRADAS → só os trechos cujo jogo é GTA 6 / GTA VI
# (capítulos da própria Twitch; nada de RP, roleplay, Cidade Alta, Complexo, GTA V) → picos de volume dentro desses trechos → cortes
# verticais de 65 s com o ÁUDIO ORIGINAL do streamer, legenda palavra por palavra e gancho → R2 privado gta/cortes/.
# Nada é postado daqui. A conta do TikTok do canal ainda não existe; a ligação com a página de aprovação vem depois, com o OK do 
#   python3 esteira_gta.py            (rodada normal)
#   python3 esteira_gta.py --listar   (só mostra o que acharia, sem baixar nada)
import json, os, re, sys, tempfile, time, urllib.request, datetime, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cortar_live as C

# 
# 
# Fora: felps ; cellbit (VOD só para inscritos); bistecone e casimiro (sem VOD na Twitch nem no Kick; estão no YouTube, que bloqueia download na nuvem).
CANAIS = {'alanzoka': 8.15, 'gaules': 4.31, 'nobru': 3.79, 'paulinholokobr': 3.71, 'yoda': 2.46, 'luquet4': 2.04, 'rakin': 1.69, 'brino': 1.63,
          'mount': 1.26, 'smzinho': 1.17, 'jovirone': 1.16, 'baiano': 1.06, 'piuzinho': 0.85, 'gordox': 0.58}   # Twitch, milhões
KICK = {'coringa': 7.27, 'jukes': 1.85}   # Kick (coringa e jukes saíram da Twitch); peso = tamanho do público dele
TESTE = os.environ.get('JOGO_RE')   # só para testar antes do lançamento (19/11) com outro jogo; tudo vai para gta/teste/
GTA6 = re.compile(TESTE or r'grand theft auto vi\b|\bgta\s*(6|vi)\b', re.I)
RP = re.compile(r'\brp\b|role\s*play|cidade alta|complexo|nopixel|fivem|\bgta\s*(5|v)\b|grand theft auto v\b', re.I)
PASTA = 'gta/teste' if TESTE else 'gta/cortes'; ESTADO = 'gta/estado-teste.json' if TESTE else 'gta/estado.json'
NAO_JOGO = re.compile(r'just chatting|conversando|music|música|special events|talk shows|pools|asmr|art\b|software|travel|food|sports|irl|slots|virtual casino', re.I)
ESTOQUE_MAX = 100                      # cortes feitos nos últimos 4 dias: acima disso a rodada não corta (economiza minutos do GitHub)
MAX_VODS, IDADE_MAX_H = 1, 72          # por rodada (o job tem 60 min); live mais velha que 3 dias não vale mais a pena
MIN_GTA_S = 20 * 60                    # trecho de GTA 6 com menos de 20 min não rende corte bom
GQL = 'https://gql.twitch.tv/gql'; CID = 'kimne78kx3ncx6brgo4mv6wki5h1ko'   # cliente público do site da Twitch (o mesmo que o yt-dlp usa)

def gql(q):
    r = urllib.request.Request(GQL, data=json.dumps({'query': q}).encode(), headers={'Client-ID': CID, 'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(r, timeout=30))['data']

def r2_json(chave, padrao):
    with tempfile.TemporaryDirectory() as d:
        if subprocess.run(['sh', C.R2, 'get', chave, f'{d}/x.json'], capture_output=True, timeout=120).returncode: return padrao
        return json.load(open(f'{d}/x.json'))

def r2_put_json(chave, obj):
    with tempfile.TemporaryDirectory() as d:
        json.dump(obj, open(f'{d}/x.json', 'w'), ensure_ascii=False, indent=1); C.sh('sh', C.R2, 'put', f'{d}/x.json', chave, capture_output=True)

def vods(canal):
    u = gql('{user(login:"%s"){videos(first:5,type:ARCHIVE,sort:TIME){edges{node{id title createdAt lengthSeconds status game{name}}}}}}' % canal)['user']
    return [e['node'] for e in (u or {}).get('videos', {}).get('edges', [])]

def vods_kick(canal):
    r = urllib.request.Request(f'https://kick.com/api/v2/channels/{canal}/videos', headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})
    out = []
    for v in json.load(urllib.request.urlopen(r, timeout=30))[:5]:
        uuid = (v.get('video') or {}).get('uuid')
        if not uuid: continue
        out.append({'id': 'k' + uuid, 'title': v.get('session_title') or '', 'createdAt': (v.get('created_at') or '').replace(' ', 'T') + 'Z',
                    'lengthSeconds': int((v.get('duration') or 0) / 1000), 'status': 'RECORDING' if v.get('is_live') else 'RECORDED',
                    'game': {'name': ((v.get('categories') or [{}])[0] or {}).get('name', '')}, 'link': v.get('source') or f'https://kick.com/{canal}/videos/{uuid}'})   # 07/11: na nuvem o extrator do Kick dá NOT_FOUND; o m3u8 direto baixa
    return out

def trechos_gta6(vod):
    # capítulos da Twitch = troca de jogo na live; sem capítulo, vale o jogo da live inteira.
    # devolve (jogo, faixas) do jogo que mais rendeu na live: GTA 6 se houver; senão o jogo com mais tempo (nunca conversa/RP/GTA V)
    link = vod.get('link') or f"https://www.twitch.tv/videos/{vod['id']}"
    if vod.get('link'):   # Kick: um jogo por live, sem capítulos
        j = (vod.get('game') or {}).get('name', '')
        if not j or RP.search(j) or NAO_JOGO.search(j) or (TESTE and not GTA6.search(j)): return ('', [])
        return ('GTA 6' if GTA6.search(j) and not TESTE else j, [(0, vod['lengthSeconds'])])
    r = subprocess.run(['yt-dlp', '-J', '--skip-download', '--no-warnings', link], capture_output=True, text=True, timeout=120)
    if 'subscriber-only' in r.stderr: return None   # VOD só para inscritos (cellbit, 07/11): não dá para baixar
    if r.returncode: raise RuntimeError(r.stderr.strip()[-200:])
    info = json.loads(r.stdout)
    caps = info.get('chapters') or [{'start_time': 0, 'end_time': vod['lengthSeconds'], 'title': (vod.get('game') or {}).get('name', '')}]
    jogos = {}
    for c in caps:
        j = (c.get('title') or '').strip()
        if j and not RP.search(j) and not NAO_JOGO.search(j): jogos.setdefault(j, []).append((int(c['start_time']), int(c['end_time'])))
    if not jogos: return ('', [])
    gta = [j for j in jogos if GTA6.search(j)]
    if TESTE and not gta: return ('', [])
    j = gta[0] if gta else max(jogos, key=lambda k: sum(f - i for i, f in jogos[k]))
    return ('GTA 6' if gta and not TESTE else j, jogos[j])

def candidatos(estado):
    agora = datetime.datetime.now(datetime.timezone.utc); out = []
    for canal in {**CANAIS, **KICK}:
        try: lista = vods_kick(canal) if canal in KICK else vods(canal)
        except Exception as e: print(canal, 'erro na Twitch:', e, flush=True); continue
        for v in lista:
            if v['id'] in estado['vistos'] or v['status'] != 'RECORDED': continue   # RECORDING = live ainda no ar
            idade = (agora - datetime.datetime.fromisoformat(v['createdAt'].replace('Z', '+00:00'))).total_seconds() / 3600
            if idade > IDADE_MAX_H and not TESTE: continue
            if re.search(r'\brerun\b|reprise', v['title'], re.I): estado['vistos'][v['id']] = {'canal': canal, 'motivo': 'reprise'}; continue
            if RP.search(v['title']): estado['vistos'][v['id']] = {'canal': canal, 'motivo': 'título com RP/GTA V'}; continue
            try: r = trechos_gta6(v)
            except Exception as e: print(canal, v['id'], 'sem capítulos:', e, flush=True); continue
            if r is None: estado['vistos'][v['id']] = {'canal': canal, 'motivo': 'VOD só para inscritos'}; continue
            jogo, tr = r
            total = sum(f - i for i, f in tr)
            if total < MIN_GTA_S: estado['vistos'][v['id']] = {'canal': canal, 'motivo': f'jogo só {total // 60} min'}; continue
            out.append((canal, v, jogo, tr, total))
    peso = {**CANAIS, **KICK}
    # 
    fresco = lambda v: (lambda h: 1 if h < 24 else 0.7 if h < 48 else 0.5)((agora - datetime.datetime.fromisoformat(v['createdAt'].replace('Z', '+00:00'))).total_seconds() / 3600)
    return sorted(out, key=lambda x: (x[2] != 'GTA 6', -peso.get(x[0], 0) * fresco(x[1])))   # GTA 6 sempre primeiro

def busca_palavra():
    """09/11: corta os momentos em que a live fala uma palavra (ex.: Neymar). Entradas: PALAVRA (regex), VOD (id da Twitch), CANAL, JOGO_NOME, TAGS, N."""
    pal = re.compile(os.environ['PALAVRA'], re.I); vod = os.environ['VOD'].rstrip('/').split('/')[-1]; canal = os.environ.get('CANAL') or 'live'
    jogo = os.environ.get('JOGO_NOME') or 'Kings League'; tags = os.environ.get('TAGS') or ''; n = int(os.environ.get('N') or 6)
    link = f'https://www.twitch.tv/videos/{vod}'
    from faster_whisper import WhisperModel
    import numpy as np
    indice = r2_json(f'{PASTA}/indice.json', [])
    with tempfile.TemporaryDirectory() as T:
        C.sh('yt-dlp', '-q', '--no-warnings', '-N', '8', '-f', 'ba/Audio_Only/worst', '-o', f'{T}/audio.%(ext)s', link, capture_output=True, text=True)
        arq = next(f'{T}/{f}' for f in os.listdir(T) if f.startswith('audio.'))
        pcm = np.frombuffer(subprocess.run(['ffmpeg', '-v', 'error', '-i', arq, '-ac', '1', '-ar', '16000', '-f', 's16le', '-'], capture_output=True, check=True).stdout, dtype=np.int16).astype(np.float32) / 32768
        print(canal, vod, f'{len(pcm) / 16000 / 60:.0f} min de áudio; procurando', pal.pattern, flush=True)
        segs, _ = WhisperModel('tiny', device='cpu', compute_type='int8', cpu_threads=os.cpu_count() or 4).transcribe(pcm, language='pt', vad_filter=True, beam_size=1, initial_prompt='Neymar, Kings League, gol, pênalti')   # 10/11: 'base' passou de 45 min em 3 h de live
        ts = [s.start for s in segs if pal.search(s.text)]; del pcm
        print('menções:', [int(t) for t in ts], flush=True)
        dens = sorted(ts, key=lambda t: -sum(abs(t - u) <= 60 for u in ts))   # onde mais se fala dele primeiro
        escolhidos = []
        for t in dens:
            if all(abs(t - e) >= C.DUR for e in escolhidos): escolhidos.append(t)
            if len(escolhidos) >= n: break
        modelo = WhisperModel('small', device='cpu', compute_type='int8')
        for t in sorted(escolhidos):
            a = max(0, int(t) - 25); nome = f'{canal}-{vod}-p{a}'
            if any(x['id'] == nome for x in indice): continue
            try: g, fala = C.cortar(link, a, nome, modelo, T, PASTA, jogo)
            except Exception as e: print(nome, 'falhou:', e, flush=True); continue
            if not g: print(nome, 'sem gancho, descartado', flush=True); continue
            ficha = {'id': nome, 'canal': canal, 'vod': vod, 'jogo': jogo, 'titulo_live': os.environ.get('TITULO', ''), 'inicio_s': a, 'gancho': g, 'fala': fala[:600],
                     'video': f'{PASTA}/{nome}.mp4', 'legenda': f'{g.capitalize()}. Corte da live do {canal} na {jogo} {tags} #cortes #{canal}'.replace('  ', ' '),
                     'criado': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'), 'estado': 'novo'}
            indice.append(ficha); r2_put_json(f'{PASTA}/indice.json', indice); print('corte pronto:', nome, '|', g, flush=True)

def montar_manual():
    """10/11: corte preparado à mão (ex.: trecho do YouTube, que não baixa na nuvem): cru.mp4 + legenda.ass + g0..g2.txt em gta/manual/<MANUAL>/; aqui só monta e indexa."""
    nome = os.environ['MANUAL']; base = f'gta/manual/{nome}'; indice = r2_json(f'{PASTA}/indice.json', [])
    with tempfile.TemporaryDirectory() as T:
        C.sh('sh', C.R2, 'get', f'{base}/cru.mp4', f'{T}/cru.mp4'); C.sh('sh', C.R2, 'get', f'{base}/legenda.ass', f'{T}/l.ass')
        topo, g = '', []
        for k in range(3):
            if subprocess.run(['sh', C.R2, 'get', f'{base}/g{k}.txt', f'{T}/g{k}.txt'], capture_output=True).returncode: break
            g.append(open(f'{T}/g{k}.txt').read().strip())
            topo += f"drawtext=fontfile='{C.FONTE}':textfile='{T}/g{k}.txt':fontsize=74:fontcolor=white:borderw=6:bordercolor=black:y_align=font:x=(w-tw)/2:y={300 + k * 92},"
        C.sh('ffmpeg', '-v', 'error', '-y', '-i', f'{T}/cru.mp4', '-filter_complex',
             f"[0:v]split[a][b];[a]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=8:2,eq=brightness=-0.15,scale={C.W}:{C.H}[f];"
             f"[b]scale={C.W}:-2[j];[f][j]overlay=0:(H-h)/2,{topo}subtitles='{T}/l.ass':fontsdir='{os.path.dirname(C.FONTE)}',format=yuv420p[v]",
             '-map', '[v]', '-map', '0:a?', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', f'{T}/{nome}.mp4', timeout=900)
        C.sh('sh', C.R2, 'put', f'{T}/{nome}.mp4', f'{PASTA}/{nome}.mp4')
    gancho = ' '.join(g)
    ficha = {'id': nome, 'canal': os.environ.get('CANAL') or 'live', 'vod': '', 'jogo': os.environ.get('JOGO_NOME') or '', 'titulo_live': os.environ.get('TITULO', ''), 'inicio_s': 0,
             'gancho': gancho, 'fala': '', 'video': f'{PASTA}/{nome}.mp4', 'legenda': f"{gancho.capitalize()} {os.environ.get('TAGS', '')}".strip(),
             'criado': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'), 'estado': 'novo'}
    indice = [x for x in indice if x['id'] != nome] + [ficha]; r2_put_json(f'{PASTA}/indice.json', indice); print('corte pronto:', nome, '|', gancho, flush=True)

if __name__ == '__main__' and os.environ.get('MANUAL'):
    montar_manual(); sys.exit(0)

if __name__ == '__main__' and os.environ.get('PALAVRA'):
    busca_palavra(); sys.exit(0)

if __name__ == '__main__':
    estado = r2_json(ESTADO, {'vistos': {}})
    cand = candidatos(estado)
    for canal, v, jogo, tr, total in cand: print(f"{canal} {v['id']} {total // 60} min de {jogo} em {len(tr)} trecho(s): {v['title'][:80]}", flush=True)
    if '--listar' in sys.argv: sys.exit(0)
    if not cand: r2_put_json(ESTADO, estado); print('nada para cortar'); sys.exit(0)
    from faster_whisper import WhisperModel
    modelo = WhisperModel('small', device='cpu', compute_type='int8')
    indice = r2_json(f'{PASTA}/indice.json', [])
    # estoque = cortes feitos nos últimos 4 dias (o estado aprovado/agendado fica na página, em gta/cortes/estado/); ~10 por dia
    lim = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=4)).isoformat()
    estoque = sum((x.get('criado') or '') > lim for x in indice)
    if estoque >= ESTOQUE_MAX and not (cand[0][2] == 'GTA 6'): r2_put_json(ESTADO, estado); print(f'estoque cheio ({estoque} cortes esperando postagem)'); sys.exit(0)
    cortadas = 0
    for canal, v, jogo, tr, total in cand:
        if cortadas >= MAX_VODS: break
        link = v.get('link') or f"https://www.twitch.tv/videos/{v['id']}"; n = max(1, min(4, total // (45 * 60)))   # ~1 corte a cada 45 min de jogo
        with tempfile.TemporaryDirectory() as T:
            # sobra de picos: os de tela parada são pulados. 07/11: VOD que não baixa (felps) não derruba a rodada; passa para a próxima live
            try: ps = C.picos_som(link, T, n * 3, faixas=tr)
            except Exception as e:
                print(canal, v['id'], 'não baixou o áudio:', str(getattr(e, 'stderr', '') or e)[-300:], flush=True)
                estado['vistos'][v['id']] = {'canal': canal, 'motivo': 'áudio não baixou'}; r2_put_json(ESTADO, estado); continue
            feitos = 0; print(canal, v['id'], 'picos:', ps, flush=True)
            for i, (p, peso) in enumerate(ps):
                if feitos >= n: break
                nome = f"{canal}-{v['id']}-{i + 1}"
                if any(x['id'] == nome for x in indice) or nome in estado.setdefault('descartados', []): continue
                try: g, fala = C.cortar(link, p - C.ANTES, nome, modelo, T, PASTA, jogo)
                except C.Parado: print(nome, 'tela parada, descartado', flush=True); estado.setdefault('descartados', []).append(nome); r2_put_json(ESTADO, estado); continue
                except Exception as e: print(nome, 'falhou:', e, flush=True); continue
                if not g: print(nome, 'sem gancho (fala sem sentido), descartado', flush=True); estado.setdefault('descartados', []).append(nome); r2_put_json(ESTADO, estado); continue   # 08/11: corte sem gancho não serve
                if len(fala.split()) < 15: print(nome, 'quase sem fala, descartado', flush=True); estado['descartados'].append(nome); r2_put_json(ESTADO, estado); continue   # corte de streamer vive da fala dele
                ficha = {'id': nome, 'canal': canal, 'vod': v['id'], 'jogo': jogo, 'titulo_live': v['title'], 'inicio_s': p - C.ANTES, 'gancho': g, 'fala': fala[:600],
                         'video': f'{PASTA}/{nome}.mp4', 'legenda': (g.capitalize() + '. ' if g else '') + f'Corte da live do {canal} no {jogo} ' + ('#gta6 #gtavi' if jogo == 'GTA 6' else '#' + re.sub(r'\W', '', jogo.lower())) + f' #cortes #{canal}',
                         'criado': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'), 'estado': 'novo'}
                feitos += 1; indice.append(ficha); r2_put_json(f'{PASTA}/indice.json', indice); print('corte pronto:', nome, flush=True)
        estado['vistos'][v['id']] = {'canal': canal, 'motivo': 'cortado', 'em': time.strftime('%Y-%m-%d %H:%M')}; cortadas += 1
        r2_put_json(ESTADO, estado)
    r2_put_json(ESTADO, estado)
