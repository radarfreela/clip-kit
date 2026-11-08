# Cortador de live (teste 07/11, .
# Live gravada do YouTube → picos do chat (a plateia vota) → baixa só esses trechos → fala transcrita palavra por palavra (Whisper)
# → corte vertical de ~65 s (jogo no meio, fundo desfocado, gancho no topo, legenda palavra por palavra) → R2 /cortes-teste/.
#   python3 cortar_live.py <link da live> [quantos cortes]
import json, os, re, subprocess, sys, tempfile, collections
R2 = os.path.expanduser('~/Development/render-kit/r2.sh')
os.environ.setdefault('R2_CRED_FILE', os.path.expanduser('~/.r2cred'))
FONTE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'fonts', 'Anton-Regular.ttf')
W, H, DUR, ANTES = 1080, 1920, 65, 50   # o chat reage ~10–20 s depois do lance: o corte começa 50 s antes do pico
def sh(*a, **k): return subprocess.run([str(x) for x in a], check=True, **k)

def picos(chat, n):
    # mensagens a cada 10 s, com peso extra para risada (kkkk) e espanto; picos a pelo menos 4 min um do outro
    bal = collections.Counter()
    for l in open(chat):
        try: a = json.loads(l)['replayChatItemAction']; ms = int(a['videoOffsetTimeMsec'])
        except Exception: continue
        txt = json.dumps(a, ensure_ascii=False).lower()
        bal[ms // 10000] += 1 + 2 * bool(re.search(r'k{4,}|kkk|hahaha|😂|🤣|mds|meu deus', txt))
    out = []
    for b, _ in bal.most_common():
        if all(abs(b - o) * 10 >= 240 for o in out) and b * 10 > ANTES: out.append(b)
        if len(out) == n: break
    return [(b * 10, bal[b]) for b in out]

def picos_som(link, T, n, faixas=None):
    # 07/11: VOD da Twitch não traz o chat pelo yt-dlp; o volume da voz do streamer (grito, risada) marca o lance
    import numpy as np
    try: sh('yt-dlp', '-q', '--no-warnings', '-N', '8', '-f', 'ba/Audio_Only/worst', '-o', f'{T}/audio.%(ext)s', link, capture_output=True, text=True)
    except subprocess.CalledProcessError:   # 07/11 (felps): "Initialization fragment found after media fragments" com download paralelo; de novo em fila
        for f in os.listdir(T):
            if f.startswith('audio.'): os.remove(f'{T}/{f}')
        sh('yt-dlp', '-q', '--no-warnings', '-f', 'ba/Audio_Only/worst', '-o', f'{T}/audio.%(ext)s', link, capture_output=True, text=True)
    arq = next(f'{T}/{f}' for f in os.listdir(T) if f.startswith('audio.'))
    x = np.frombuffer(subprocess.run(['ffmpeg', '-v', 'error', '-i', arq, '-ac', '1', '-ar', '8000', '-f', 's16le', '-'], capture_output=True, check=True).stdout, dtype=np.int16).astype(np.float32)
    rms = np.sqrt(np.mean(x[: len(x) // 80000 * 80000].reshape(-1, 80000) ** 2, axis=1))   # 10 s por bloco
    base = np.convolve(rms, np.ones(30) / 30, 'same') + 1   # comparado com os 5 min em volta (não premia trecho só com música alta)
    nota = rms / base; out = []
    dentro = lambda b: faixas is None or any(i + ANTES <= b * 10 <= f - (DUR - ANTES) for i, f in faixas)   # o corte inteiro cai dentro do trecho de GTA 6
    for b in np.argsort(-nota):
        if all(abs(int(b) - o) * 10 >= 240 for o in out) and b * 10 > ANTES and dentro(int(b)): out.append(int(b))
        if len(out) == n: break
    return [(b * 10, round(float(nota[b]), 2)) for b in out]

def legenda_ass(palavras, arq):
    # palavra por palavra, 3 por vez, a que está sendo falada em amarelo; faixa de baixo (longe do gancho do topo)
    cab = ('[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Outline, Shadow, Alignment, MarginV\n'
           'Style: L,Anton,84,&H00FFFFFF,&H00000000,&H80000000,0,6,0,2,430\n\n[Events]\nFormat: Layer, Start, End, Style, Text\n')
    t = lambda s: f'{int(s // 3600)}:{int(s % 3600 // 60):02d}:{s % 60:05.2f}'
    linhas = []
    for i in range(0, len(palavras), 3):
        g = palavras[i:i + 3]
        for j, (w, a, b) in enumerate(g):
            fim = g[j + 1][1] if j + 1 < len(g) else b
            txt = ' '.join(('{\\c&H00FFFF&}' + x.upper() + '{\\c&HFFFFFF&}') if k == j else x.upper() for k, (x, _, _) in enumerate(g))
            linhas.append(f'Dialogue: 0,{t(a)},{t(max(fim, a + 0.05))},L,{txt}')
    open(arq, 'w').write(cab + '\n'.join(linhas) + '\n')

def gancho(texto, jogo='GTA 6'):
    # título curto do corte a partir do que foi falado (opcional: sem chave, sai sem gancho)
    if not os.environ.get('ANTHROPIC_API_KEY') or len(texto.split()) < 8: return ''   # trecho sem fala: sem gancho (o 1º teste inventou "não veio transcrição")
    import anthropic
    for _ in range(2):   # 08/11: 2 cortes saíram sem gancho (resposta vazia); tenta de novo antes de desistir
      g = _gancho(texto, jogo)
      if g: return g
    return ''

def _gancho(texto, jogo):
    import anthropic
    r = anthropic.Anthropic(timeout=60, max_retries=1).messages.create(model='claude-sonnet-5-5', max_tokens=400, messages=[{'role': 'user', 'content':
        f'Isto é a fala transcrita de um trecho de live de {jogo} de um streamer brasileiro. Escreva UM gancho para o topo do corte vertical, em português do Brasil, '
        'maiúsculas, no máximo 7 palavras, sem emoji, sem hashtag, começando direto pela AÇÃO, sem sujeito genérico (nunca "streamer", "gamer", "jogador", "ele"); exemplo bom: "FECHOU O JOGO E ESPEROU O CHAT FALAR"; curioso e fiel ao que ELE FALA no trecho; não invente fato que não está na fala. Responda só o gancho.\n\n' + texto[:4000]}])
    txt = ''.join(b.text for b in r.content if getattr(b, 'type', '') == 'text')   # a resposta pode vir com bloco de raciocínio antes do texto
    g = next((l for l in txt.strip().splitlines() if l.strip()), '').strip().strip('"').upper()   # 07/11: veio texto extra numa 2ª linha; só a 1ª vale
    g = re.sub(r'^(O |A )?(STREAMER|GAMER|JOGADOR|JOGADORA|ELE|ELA)\s+', '', g)   # 
    return g[:60]


class Parado(Exception): pass

def parado(arq):
    """fração do trecho com a imagem congelada (menu aberto, pausa, tela de 'já volto'); a câmera pequena do streamer quase não conta"""
    r = subprocess.run(['ffmpeg', '-v', 'info', '-i', arq, '-vf', 'fps=2,scale=320:-2,freezedetect=n=0.004:d=2', '-an', '-f', 'null', '-'], capture_output=True, text=True, timeout=300)
    seg = sum(float(x) for x in re.findall(r'freeze_duration: ([\d.]+)', r.stderr))
    ini = [float(x) for x in re.findall(r'freeze_start: ([\d.]+)', r.stderr)]; fim = re.findall(r'freeze_end', r.stderr)
    if len(ini) > len(fim): seg += DUR - ini[-1]   # congelado até o fim do trecho
    return seg / DUR

def cortar(link, a, nome, modelo, T, destino, jogo='GTA 6'):
    """baixa [a, a+DUR] da live, legenda palavra por palavra, gancho no topo, envia ao R2 em <destino>/<nome>.mp4; devolve (gancho, fala)."""
    # 07/11: 1080p + recodificar no download levava ~10 min por corte; agora 720p, 10 s de sobra antes e o corte exato no ffmpeg
    a0 = max(0, a - 10)
    sh('yt-dlp', '-q', '--no-warnings', '-N', '8', '-f', 'bv*[height<=720]+ba/b[height<=720]/b', '--download-sections', f'*{a0}-{a + DUR + 2}', '--merge-output-format', 'mp4', '-o', f'{T}/{nome}-bruto.mp4', link)
    sh('ffmpeg', '-v', 'error', '-y', '-ss', f'{a - a0}', '-i', f'{T}/{nome}-bruto.mp4', '-t', DUR, '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '18', '-c:a', 'aac', '-b:a', '192k', f'{T}/{nome}-cru.mp4', timeout=300)
    if parado(f'{T}/{nome}-cru.mp4') > 0.4: raise Parado(nome)   # 
    import numpy as np   # 07/11: o PyAV novo quebrou a leitura do faster-whisper; o áudio entra já decodificado pelo ffmpeg
    pcm = np.frombuffer(subprocess.run(['ffmpeg', '-v', 'error', '-i', f'{T}/{nome}-cru.mp4', '-ac', '1', '-ar', '16000', '-f', 's16le', '-'], capture_output=True, check=True).stdout, dtype=np.int16).astype(np.float32) / 32768
    segs, _ = modelo.transcribe(pcm, language='pt', word_timestamps=True, vad_filter=True)
    palavras, fala = [], []
    for s in segs:
        fala.append(s.text)
        for w in s.words or []: palavras.append((w.word.strip(), w.start, w.end))
    legenda_ass(palavras, f'{T}/{nome}.ass'); g = gancho(' '.join(fala), jogo)
    lin, l = [], ''   # gancho em até 2 linhas de ~18 letras (no teste passou da largura da tela)
    for w in g.split():
        if len(l + ' ' + w) > 18 and l: lin.append(l); l = w
        else: l = (l + ' ' + w).strip()
    # 07/11: o ffmpeg 8 desenhava a quebra de linha como um quadradinho; agora um drawtext por linha
    topo = ''
    for k, t in enumerate((lin + [l]) if g else []):
        open(f'{T}/{nome}-g{k}.txt', 'w').write(t)
        topo += f"drawtext=fontfile='{FONTE}':textfile='{T}/{nome}-g{k}.txt':fontsize=74:fontcolor=white:borderw=6:bordercolor=black:y_align=font:x=(w-tw)/2:y={300 + k * 92},"
    sh('ffmpeg', '-v', 'error', '-y', '-i', f'{T}/{nome}-cru.mp4', '-filter_complex',
       f"[0:v]split[a][b];[a]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=8:2,eq=brightness=-0.15,scale={W}:{H}[f];"
       f"[b]scale={W}:-2[j];[f][j]overlay=0:(H-h)/2,{topo}subtitles='{T}/{nome}.ass':fontsdir='{os.path.dirname(FONTE)}',format=yuv420p[v]",
       '-map', '[v]', '-map', '0:a?', '-t', DUR, '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', f'{T}/{nome}.mp4', timeout=600)
    sh('sh', R2, 'put', f'{T}/{nome}.mp4', f'{destino}/{nome}.mp4')
    return g, ' '.join(fala)

if __name__ == '__main__':
    link, n = sys.argv[1], int(sys.argv[2]) if sys.argv[2:] else 3
    from faster_whisper import WhisperModel
    modelo = WhisperModel('small', device='cpu', compute_type='int8')
    with tempfile.TemporaryDirectory() as T:
        try:
            sh('yt-dlp', '-q', '--no-warnings', '--skip-download', '--write-subs', '--sub-langs', 'live_chat', '-o', f'{T}/live', link)
            ps = picos(f'{T}/live.live_chat.json', n); print('picos do chat (segundo, peso):', ps, flush=True)
        except Exception:   # sem chat gravado (Twitch): os momentos em que o streamer grita/ri mais alto
            ps = picos_som(link, T, n); print('picos do som (segundo, volume):', ps, flush=True)
        for i, (p, peso) in enumerate(ps):
            a = p - ANTES; nome = f'corte{i + 1}'
            g, fala = cortar(link, a, nome, modelo, T, 'gta/teste')
            print(json.dumps({'corte': nome, 'inicio_s': a, 'pico': peso, 'gancho': g, 'fala': fala[:300]}, ensure_ascii=False), flush=True)
