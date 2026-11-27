import json
import os
import random
import shutil
import time
import urllib.request
import zipfile
import re
from pathlib import Path
import stripe
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

stripe.api_key = os.getenv("STRIPE_API_KEY")

WEBHOOK_KEY =os.getenv("WEBHOOK_KEY")

with open("workflow_img.json", "r") as f:
    workflow_img = json.load(f)

with open("workflow_video.json", "r") as f:
    workflow_video = json.load(f)

with open("workflow_continua_video.json", "r") as f:
    workflow_continua_video = json.load(f)

order_number = 0
temp_prompts = {}

def genera_contenuti(order, tipo, prompt, durata=False):
    global workflow_img, workflow_video, workflow_continua_video
    if tipo == "img":
        workflow_img["30:19"]["inputs"]["value"] = prompt
        workflow_img["30:3"]["inputs"]["seed"] = random.randint(1, 999999999)
        
        data = json.dumps({"prompt": workflow_img}).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:8188/prompt",
            data=data,
            headers = {"Content-Type": "application/json"}
        )
        res = json.loads(urllib.request.urlopen(req).read())
        prompt_id = res["prompt_id"]

        while True:
            hist_res = json.loads(urllib.request.urlopen(f"http://127.0.0.1:8188/history/{prompt_id}").read())
            if prompt_id in hist_res:
                outputs = hist_res[prompt_id]["outputs"]
                break
            time.sleep(0.5)

    if tipo == "video":
        if durata:
            frasi = [f.strip() for f in re.split(r'(?<=[.!?])\s+', prompt.strip()) if f.strip()]
            #frasi = [
            #    f"{frasi[i]} + {frasi[i+1]}" if i + 1 < len(frasi) else frasi[i]
            #    for i in range(0, len(frasi), 2)
            #]
            prompt_tmp = frasi[0]
            frasi.pop(0)
        workflow_video["405:376"]["inputs"]["value"] = prompt
        workflow_video["405:338"]["inputs"]["noise_seed"] = random.randint(1, 999999999)
        workflow_video["405:339"]["inputs"]["noise_seed"] = random.randint(1, 999999999)
        
        data = json.dumps({"prompt": workflow_video}).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:8188/prompt",
            data=data,
            headers = {"Content-Type": "application/json"}
        )
        res = json.loads(urllib.request.urlopen(req).read())
        prompt_id = res["prompt_id"]

        while True:
            hist_res = json.loads(urllib.request.urlopen(f"http://127.0.0.1:8188/history/{prompt_id}").read())
            if prompt_id in hist_res:
                outputs = hist_res[prompt_id]["outputs"]
                break
            time.sleep(0.5)

        if durata:
            while len(frasi) != 0:
                nome_file = [f["filename"] for o in outputs.values() for v in o.values() if isinstance(v, list) for f in v if isinstance(f, dict) and "filename" in f][0]
                path_video = os.path.join(r"C:\Users\moran\AppData\Local\Comfy-Desktop\ComfyUI-Shared\output", nome_file)
                temp_path = os.path.join(r"C:\Users\moran\AppData\Local\Comfy-Desktop\ComfyUI-Shared\input", nome_file) + ".png"
                os.system(f'ffmpeg -y -sseof -1 -i "{path_video}" -update 1 -q:v 1 "{temp_path}"')
                prompt_temp = prompt + f'. La parte che devi generare è "{frasi[0]}". Assicurati che in base al prompt precedente non sbagli a creare personaggi, animali, audio o altre cose del genere.'
                workflow_continua_video["395"]["inputs"]["image"] = nome_file + ".png"
                workflow_continua_video["398:376"]["inputs"]["value"] = prompt_temp
                workflow_continua_video["398:339"]["inputs"]["noise_seed"] = random.randint(1, 999999999)
                workflow_continua_video["398:338"]["inputs"]["noise_seed"] = random.randint(1, 999999999)

                data = json.dumps({"prompt": workflow_continua_video}).encode("utf-8")
                req = urllib.request.Request(
                    "http://127.0.0.1:8188/prompt",
                    data=data,
                    headers = {"Content-Type": "application/json"}
                )
                res = json.loads(urllib.request.urlopen(req).read())
                prompt_id = res["prompt_id"]

                while True:
                    hist_res = json.loads(urllib.request.urlopen(f"http://127.0.0.1:8188/history/{prompt_id}").read())
                    if prompt_id in hist_res:
                        outputs = hist_res[prompt_id]["outputs"]
                        break
                    time.sleep(0.5)

                frasi.pop(0)

            out_dir = Path(r"C:\Users\moran\AppData\Local\Comfy-Desktop\ComfyUI-Shared\output")
            final_path = Path(r"C:\Users\moran\AppData\Local\Comfy-Desktop\ComfyUI-Shared\output\output.mp4")
            clips = sorted(out_dir.glob("*.mp4"))
            n = len(clips)

            if n == 1:
                os.system(f'ffmpeg -y -i "{clips}" -c copy "{final_path}"')
            elif n > 1:
                ins = " ".join(f'-i "{c}"' for c in clips)
                v_cat = "".join(f"[{i}:v]" for i in range(n)) + f"concat=n={n}:v=1:a=0[v];"
                a_cat = "".join(f"{'[0:a]' if i==1 else f'[a{i-1}]'}[{i}:a]acrossfade=d=0.3{'[a]' if i==n-1 else f'[a{i}]'};" for i in range(1, n))
                os.system(f'ffmpeg -y {ins} -filter_complex "{v_cat}{a_cat[:-1]}" -map "[v]" -map "[a]" "{final_path}"')

            for c in clips:
                c.unlink()


    shutil.rmtree(r"C:\Users\moran\AppData\Local\Comfy-Desktop\ComfyUI-Shared\temp")
    os.makedirs(r"C:\Users\moran\AppData\Local\Comfy-Desktop\ComfyUI-Shared\temp", exist_ok=True)

    shutil.make_archive(
        rf"C:\Users\moran\Documents\Progetti\apiLc\files\order_{order}",
        "zip",
        root_dir=r"C:\Users\moran\AppData\Local\Comfy-Desktop\ComfyUI-Shared\output",
        base_dir="."
    )

    shutil.rmtree(r"C:\Users\moran\AppData\Local\Comfy-Desktop\ComfyUI-Shared\output")
    os.makedirs(r"C:\Users\moran\AppData\Local\Comfy-Desktop\ComfyUI-Shared\output", exist_ok=True)
    shutil.rmtree(r"C:\Users\moran\AppData\Local\Comfy-Desktop\ComfyUI-Shared\input")
    os.makedirs(r"C:\Users\moran\AppData\Local\Comfy-Desktop\ComfyUI-Shared\input", exist_ok=True)

    return {"status": "ok", "order": order}

class FormeDati(BaseModel):
    tipo: str
    quantita: int
    prompt: str
    durata: bool = False

@app.post("/order")
async def genera_checkout(dati: FormeDati):
    global order_number
    prezzo = 0
    if dati.tipo == "img":
        if dati.quantita < 1000:
            prezzo = dati.quantita * 0.01 * 100
        elif dati.quantita == 1000:
            prezzo = 500
        elif dati.quantita == 2500:
            prezzo = 1000
        elif dati.quantita == 5000:
            prezzo = 1500
        else:
            return {"status": "error"}
    elif dati.tipo == "video":
        prezzo = len([f.strip() for f in re.split(r'(?<=[.!?])\s+', dati.prompt.strip()) if f.strip()])/12 * 100
    else:
        return {"status": "error"}

    if prezzo < 100:
        prezzo = 100
        
    order_number += 1
    temp_prompts[str(order_number)] = dati.prompt
    
    session = stripe.checkout.Session.create(
        line_items=[{
            "price_data": {
                "currency": "eur",
                "product_data": {
                    "name": "apiLc Generazioni IA",
                },
                "unit_amount": int(round(prezzo)),
            },
            "quantity": 1,
        }],
        mode="payment",
        metadata = {
            "order": str(order_number),
            "tipo": dati.tipo,
            "durata": str(dati.durata)
        },
        success_url="http://localhost:8000/successo",
        cancel_url="http://localhost:8000/annullato",
    )

    return {"status": "ok", "url": session.url}

@app.post("/webhook/stripe")
async def stripe_webhook(request: Request, background_tasks: BackgroundTasks):
    global temp_prompts
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_KEY)
    except:
        raise HTTPException(status_code=400, detail="Tentata falsificazione di pagamento")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        meta = session["metadata"]

        order = meta["order"]
        tipo = meta["tipo"]
        durata = bool(meta["durata"])

    background_tasks.add_task(genera_contenuti, str(order), tipo, temp_prompts[str(order)], durata)
    temp_prompts.pop(str(order), None)

    return {"status": "ok"}

# print(genera_contenuti("999", "video", "Un ratto gigante insegue una donna attraente che sta correndo via da lui. La donna attraente urla in italiano SASA, TOMINO! La donna attraente recupera un lanciarazzi e distrugge un muro urlando BAZUKA! Ora appare dal nulla un ragazzo di 12 anni russo che dice CIAO SONO SASA", durata=True))
