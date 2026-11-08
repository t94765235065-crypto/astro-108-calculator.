import datetime as dt
import math
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
import swisseph as swe
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder

st.set_page_config(page_title="Возрастные контакты — 108 лет", layout="wide", page_icon="✦")
st.title("✦ Возрастные контакты — 108 лет")
st.caption("Самостоятельный калькулятор · натальная карта · малые точки жизни и кризиса")

@st.cache_data(show_spinner=False, ttl=86400)
def locate(city):
    p=Nominatim(user_agent="astro108-calculator").geocode(city, timeout=15)
    if p is None: raise ValueError("Населённый пункт не найден. Укажите страну и регион.")
    zone=TimezoneFinder().timezone_at(lat=p.latitude,lng=p.longitude)
    if not zone: raise ValueError("Часовой пояс не определён.")
    return p.address,p.latitude,p.longitude,zone

BODIES=[("Солнце",swe.SUN),("Луна",swe.MOON),("Меркурий",swe.MERCURY),
("Венера",swe.VENUS),("Марс",swe.MARS),("Юпитер",swe.JUPITER),
("Сатурн",swe.SATURN),("Уран",swe.URANUS),("Нептун",swe.NEPTUNE),
("Плутон",swe.PLUTO),("Северный узел",swe.MEAN_NODE),
("Чёрная Луна (средняя)",swe.MEAN_APOG)]

def natal(utc,lat,lon,house):
    jd=swe.julday(utc.year,utc.month,utc.day,utc.hour+utc.minute/60+utc.second/3600)
    positions={}
    for name,code in BODIES:
        positions[name]=swe.calc_ut(jd,code,swe.FLG_MOSEPH)[0][0]%360
    positions["Южный узел"]=(positions["Северный узел"]+180)%360
    cusps,angles=swe.houses_ex(jd,lat,lon,house.encode("ascii"))
    for i,x in enumerate(cusps,1):positions[f"Куспид {i} дома"]=x%360
    return positions

def contacts(positions,birth,orb,years):
    rows=[]
    for label,longitude in positions.items():
        for name,cycle,direction in [("Малая точка жизни",7,1),("Малая точка кризиса",9,-1)]:
            phase=(longitude%360)/360 if direction==1 else ((360-longitude)%360)/360
            for k in range(math.ceil(years/cycle)+1):
                age=cycle*(phase+k)
                if age>years:continue
                exact=birth+dt.timedelta(days=age*365.2425)
                half=dt.timedelta(days=orb*cycle*365.2425/360)
                rows.append({"Возраст":round(age,3),"Точка":name,"Натальный показатель":label,
                "Точный контакт":exact.date(),"Начало периода":(exact-half).date(),
                "Конец периода":(exact+half).date(),"Дней действия":round(2*half.total_seconds()/86400,1)})
    return pd.DataFrame(rows).sort_values("Точный контакт").reset_index(drop=True)

with st.sidebar:
    st.header("Данные рождения")
    city=st.text_input("Город и страна","Ростов-на-Дону, Россия")
    date=st.date_input("Дата рождения",dt.date(1990,9,5),min_value=dt.date(1800,1,1),max_value=dt.date(2100,12,31),format="DD.MM.YYYY")
    time=st.time_input("Время рождения",dt.time(11,52,38),step=1)
    system=st.selectbox("Система домов",["Плацид","Кох","Равнодомная"])
    orb=st.select_slider("Орбис (± градусов)",options=[0.5,1.0,2.0],value=1.0)
    years=st.slider("Лет прогноза",7,108,108)
    st.caption("Дополнительные долготы 0–360°, если известны")
    extras={x:st.text_input(x,"") for x in ["Хирон","Селена","Жребий Фортуны"]}
    calculate=st.button("Рассчитать",type="primary",use_container_width=True)

if calculate:
    try:
        address,lat,lon,tz=locate(city)
        naive=dt.datetime.combine(date,time)
        local=naive.replace(tzinfo=ZoneInfo(tz))
        if local.replace(fold=0).utcoffset()!=local.replace(fold=1).utcoffset():
            raise ValueError("Неоднозначное местное время при переводе часов. Требуется уточнить UTC-смещение.")
        utc=local.astimezone(dt.timezone.utc)
        if utc.astimezone(ZoneInfo(tz)).replace(tzinfo=None)!=naive:
            raise ValueError("Такого местного времени не существовало из-за перевода часов.")
        code={"Плацид":"P","Кох":"K","Равнодомная":"E"}[system]
        pos=natal(utc,lat,lon,code)
        for label,value in extras.items():
            if value.strip():
                longitude=float(value.replace(",","."))
                if not 0<=longitude<360:raise ValueError(label+": требуется значение от 0 до 360")
                pos[label]=longitude
        df=contacts(pos,naive,orb,years)
        st.session_state["result"]=(df,pos,address,tz,utc)
    except Exception as e:st.error(str(e))

if "result" in st.session_state:
    df,pos,address,tz,utc=st.session_state["result"]
    st.success(f"{address} · {tz} · UTC {utc:%d.%m.%Y %H:%M}")
    a,b,c=st.columns(3)
    a.metric("Контактов",len(df))
    b.metric("Жизнь",sum(df["Точка"]=="Малая точка жизни"))
    c.metric("Кризис",sum(df["Точка"]=="Малая точка кризиса"))
    tab1,tab2,tab3=st.tabs(["Все контакты","Активные на дату","Натальная карта"])
    with tab1:
        ages=st.slider("Возраст",0,108,(30,45))
        types=st.multiselect("Точки",df["Точка"].unique(),default=list(df["Точка"].unique()))
        targets=st.multiselect("Показатели",list(pos),default=list(pos))
        shown=df[df["Возраст"].between(*ages)&df["Точка"].isin(types)&df["Натальный показатель"].isin(targets)]
        st.dataframe(shown,hide_index=True,use_container_width=True,height=500)
        st.download_button("Скачать CSV",df.to_csv(index=False,sep=";").encode("utf-8-sig"),"contacts_108.csv","text/csv")
    with tab2:
        selected=st.date_input("Проверить дату",dt.date.today(),key="check_date")
        active=df[(df["Начало периода"]<=selected)&(df["Конец периода"]>=selected)]
        st.metric("Активных контактов",len(active))
        st.dataframe(active,hide_index=True,use_container_width=True)
    with tab3:
        st.dataframe(pd.DataFrame([{"Показатель":k,"Долгота":round(v,5)} for k,v in pos.items()]),hide_index=True,use_container_width=True)
else:
    st.info("Введите место, дату и время рождения и нажмите «Рассчитать».")

st.caption("Swiss Ephemeris / Moshier; исторический часовой пояс IANA. Время и координаты проверяйте для старых и неоднозначных населённых пунктов. Даты контактов рассчитаны по условному году 365,2425 суток и выбранному орбису; это модель, не доказанный период влияния. Хирон, Селена и Фортуна вводятся вручную.")
