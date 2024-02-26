from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import json, os, pytz, requests, logging
from gpt_researcher.utils.websocket_manager import WebSocketManager
from .utils import write_md_to_pdf
from dotenv import load_dotenv
from datetime import datetime as dtdt

load_dotenv()

ODDSAPI_API_KEY=os.getenv('ODDS_API_KEY')
OPENAI_API_KEY=os.getenv("OPENAI_API_KEY")
ept = pytz.timezone('US/Eastern')
utc = pytz.utc
# str format
fmt = '%Y-%m-%d %H:%M:%S %Z%z'

class ResearchRequest(BaseModel):
    task: str
    report_type: str
    agent: str


app = FastAPI()

app.mount("/site", StaticFiles(directory="./frontend"), name="site")
app.mount("/static", StaticFiles(directory="./frontend/static"), name="static")

templates = Jinja2Templates(directory="./frontend")

manager = WebSocketManager()


# Dynamic directory for outputs once first research is run
@app.on_event("startup")
def startup_event():
    if not os.path.isdir("outputs"):
        os.makedirs("outputs")
    app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")

@app.get("/")
async def read_root(request: Request):
    sports = ['soccer_usa_mls','basketball_nba','americanfootball_nfl','icehockey_nhl','basketball_ncaab','soccer_epl','tennis_atp_aus_open_singles','tennis_wta_aus_open_singles','soccer_africa_cup_of_nations','soccer_spain_la_liga']
    #sports = ['americanfootball_ncaaf', 'baseball_mlb_preseason', 'baseball_ncaa', 'basketball_nba', 'basketball_ncaab', 'boxing_boxing', 'icehockey_nhl', 'mma_mixed_martial_arts', 'soccer_australia_aleague', 'soccer_epl', 'soccer_fa_cup', 'soccer_spain_la_liga', 'soccer_usa_mls']
    #sports = []
    #sportsReq = requests.get(f"https://api.the-odds-api.com/v4/sports/?apiKey={ODDSAPI_API_KEY}")
    #sports_json = sportsReq.json()
    #for i in range(len(sports_json)):
    #    sports.append(sports_json[i]['key'])
    #print(sports)

    dataGames = []
    #dataGames.append("ai_sportsbetting" + " - " + "Write an article announcing GPT Sportswriter an AI Sports Betting Prediction Machine.")
    for sport in sports:
        dataMatch = requests.get(f"https://api.the-odds-api.com/v4/sports/{sport}/odds/?apiKey={ODDSAPI_API_KEY}&regions=us&markets=h2h&bookmakers=draftkings,fanduel")
        dataMatch = dataMatch.json()
        print(dataMatch)
        for i in range(len(dataMatch)):
            #utcTime = dtdt(dataMatch[i]['commence_time'], tzinfo=utc)
            try:
                t = dataMatch[i]['commence_time']
            except:
                t = "2024-02-25 12:00:00-05:00"
            utcTime = dtdt(int(t[0:4]), int(t[5:7]), int(t[8:10]), int(t[11:13]), int(t[14:16]), int(t[17:19]), tzinfo=utc)
            #print(utcTime)
            esTime = utcTime.astimezone(ept)
            #print(esTime)
            dataGames.append(dataMatch[i]['sport_key'] + " - " + dataMatch[i]['away_team'] + " VS " + dataMatch[i]['home_team'] + " Prediction " + str(esTime))

    for sport in sports:
        dataResults = requests.get(f"https://api.the-odds-api.com/v4/sports/{sport}/scores/?daysFrom=1&apiKey={ODDSAPI_API_KEY}")
        dataResults = dataResults.json()
        try:
            for i in range(len(dataResults)):
                if dataResults[i]['completed']:
                    t = dataResults[i]['commence_time']
                    utcTime = dtdt(int(t[0:4]), int(t[5:7]), int(t[8:10]), int(t[11:13]), int(t[14:16]), int(t[17:19]), tzinfo=utc)
                    #print(utcTime)
                    esTime = utcTime.astimezone(ept)
                    dataGames.append(dataResults[i]['sport_key'] + " - " + dataResults[i]['home_team'] + " VS " + dataResults[i]['away_team'] + " Recap " + str(esTime)) 
                else:
                    logging.warning("error")      
        except:
            logging.warning("error")
        
        
    print(dataGames)

    return templates.TemplateResponse('index.html', {"request": request, "report": None, "dataMatch": dataGames})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data.startswith("start"):
                json_data = json.loads(data[6:])
                task = json_data.get("task")
                report_type = json_data.get("report_type")
                sport_key = task.split(' ', 1)
                dataScores = requests.get(f"https://api.the-odds-api.com/v4/sports/{sport_key[0]}/scores/?daysFrom=1&apiKey={ODDSAPI_API_KEY}")
                data_scores = dataScores.json()
                dataOdds = requests.get(f"https://api.the-odds-api.com/v4/sports/{sport_key[0]}/odds/?apiKey={ODDSAPI_API_KEY}&regions=us&markets=h2h&bookmakers=draftkings,fanduel")
                data_odds = dataOdds.json()
                if task and report_type:
                    report = await manager.start_streaming(task, report_type, websocket)
                    path = await write_md_to_pdf(report)
                    await websocket.send_json({"type": "path", "output": path})
                else:
                    print("Error: not enough parameters provided.")

    except WebSocketDisconnect:
        await manager.disconnect(websocket)

