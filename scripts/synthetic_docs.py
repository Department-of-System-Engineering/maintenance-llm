# scripts/synthetic_docs.py
"""
Szintetikus karbantartási dokumentumok (HTML formában) a demó tudásbázishoz.

FIGYELEM: minden itt szereplő gép, cikkszám, érték és eljárás KITALÁLT.
Nem valós üzemi utasítás — kizárólag a RAG pipeline teszteléséhez készült.
A gépek és hibakódok egyeznek a generate_synthetic_data.py által
előállított t_cmms_wo munkalapokkal, így a dokumentum- és az SQL-ág
ugyanarról a (kitalált) üzemről szól.
"""

DISCLAIMER = (
    "SZINTETIKUS TESZTDOKUMENTUM – a szakdolgozati demóhoz generálva, "
    "nem valós üzemi utasítás."
)

# fájlnév -> (cím, HTML törzs)
DOCUMENTS = {
    "MWI-90101_JR2020_Eszterga_Foorso_kenes_hibaelharitas.pdf": (
        "MWI-90101 – JR20/20 eszterga: főorsó kenési rendszer hibaelhárítása",
        """
<p><b>Dokumentum azonosító:</b> MWI-90101 &nbsp; <b>Verzió:</b> 3 &nbsp; <b>Hatályos:</b> 2025.03.01.<br/>
<b>Részleg:</b> Forgácsolás (Machining) &nbsp; <b>Gép:</b> JR20/20 CNC eszterga<br/>
<b>Érintett gépszámok:</b> #100, #105, #200</p>

<h2>1. Cél</h2>
<p>Az utasítás leírja a főorsó kenési rendszer felépítését, a „FŐORSÓ KENÉS NYOMÁS ALACSONY”
(riasztáskód: <b>2041</b>) hibaüzenet lehetséges okait és a hibaelhárítás lépéseit.</p>

<h2>2. A kenési rendszer felépítése</h2>
<ul>
<li>Olajtartály: 20 l, kenőanyag: <b>ATF (Dexron III)</b></li>
<li>Fogaskerék-szivattyú, villanymotor 0,37 kW, rugalmas tengelykapcsolóval</li>
<li>Szívóoldali szűrő (szita, 150 µm) – cikkszám: KS-150-JR</li>
<li>Nyomóoldali szűrőbetét (10 µm) eltömődés-jelzővel – cikkszám: NSZ-10-JR</li>
<li>Nyomáshatároló szelep, beállítási érték: 4,0 bar</li>
<li>Nyomáskapcsoló (PS-41), kapcsolási pont: 1,8 bar</li>
<li>Olajhűtő (lég-olaj hőcserélő) ventilátorral</li>
</ul>
<p><b>Üzemi kenőnyomás:</b> 2,5–3,5 bar. <b>Riasztás:</b> 1,8 bar alatt, 5 másodperc késleltetéssel;
a vezérlés ilyenkor letiltja a főorsót (2041-es riasztás).<br/>
<b>Üzemi olajhőmérséklet:</b> 25–45 °C. 50 °C felett „KENŐOLAJ HŐMÉRSÉKLET MAGAS” (2042) figyelmeztetés.</p>

<h2>3. Az alacsony kenőnyomás lehetséges okai</h2>
<table>
<tr><th>#</th><th>Ok</th><th>Jellemző tünet</th><th>Ellenőrzés</th></tr>
<tr><td>1</td><td>Alacsony olajszint</td><td>Nyomás lassan csökken, szivattyú zajos</td><td>Szintjelző üveg, minimum jel felett kell lennie</td></tr>
<tr><td>2</td><td>Eltömődött szívószűrő</td><td>Szivattyú kavitál, „sípoló” hang</td><td>Szűrő kiszerelése, szemrevételezés</td></tr>
<tr><td>3</td><td>Eltömődött nyomóoldali szűrőbetét</td><td>Eltömődés-jelző piros</td><td>Jelző állapota, betétcsere</td></tr>
<tr><td>4</td><td>Kopott fogaskerék-szivattyú</td><td>Nyomás melegen csökken, hidegen még megfelelő</td><td>Szállított mennyiség mérése (min. 1,2 l/perc)</td></tr>
<tr><td>5</td><td>Elnyíródott tengelykapcsoló</td><td>Motor forog, nyomás 0 bar</td><td>Tengelykapcsoló szemrevételezése</td></tr>
<tr><td>6</td><td>Nyomáshatároló szelep beragadt / elállítódott</td><td>Nyomás állandóan alacsony, olaj visszafolyik a tartályba</td><td>Beállítási érték ellenőrzése manométerrel</td></tr>
<tr><td>7</td><td>Tömítetlen csatlakozás, csőtörés</td><td>Olajfolt a gép alatt, szint fogy</td><td>Csővezeték és csatlakozások szemrevételezése</td></tr>
<tr><td>8</td><td>Hibás nyomáskapcsoló vagy vezeték</td><td>Manométer szerint a nyomás megfelelő, mégis riaszt</td><td>Kapcsoló bemenet ellenőrzése a PLC diagnosztikában (I12.3)</td></tr>
<tr><td>9</td><td>Túl hideg olaj (hétfői indulás)</td><td>Indításkor riaszt, bemelegedés után megszűnik</td><td>Olajhőmérséklet, bemelegítő program futtatása</td></tr>
</table>

<h2>4. Hibaelhárítás lépései</h2>
<ol>
<li>A gépet állítsa le, és végezze el az energiamentesítést a BIZ-001 szerint.</li>
<li>Ellenőrizze az olajszintet a szintjelző üvegen. Ha a minimum jel alatt van, töltsön utána ATF olajjal, és keresse meg a fogyás okát (7. ok).</li>
<li>Ellenőrizze a nyomóoldali szűrő eltömődés-jelzőjét. Ha piros, cserélje a szűrőbetétet (NSZ-10-JR).</li>
<li>Szerelje ki és tisztítsa meg a szívószűrőt (KS-150-JR) tisztítószerrel és sűrített levegővel. Sérült szitát cseréljen.</li>
<li>Csatlakoztasson ellenőrző manométert (0–10 bar) a mérőcsonkra, és indítsa a kenőszivattyút kézi üzemben (MDI: M131).</li>
<li>Ha a nyomás 2,5 bar alatt van, ellenőrizze a nyomáshatároló szelepet; szükség esetén állítsa be 4,0 bar-ra.</li>
<li>Ha a motor forog, de nincs nyomás, ellenőrizze a tengelykapcsolót, majd mérje meg a szivattyú szállítását. 1,2 l/perc alatt a szivattyút cserélni kell (cikkszám: FSZ-JR-02).</li>
<li>Ha a manométer megfelelő nyomást mutat, de a riasztás fennáll, ellenőrizze a PS-41 nyomáskapcsolót és bekötését.</li>
<li>Javítás után 10 percig járassa a főorsót 500 1/perc fordulaton, és ellenőrizze a nyomást és a szivárgásmentességet.</li>
<li>Rögzítse a CMMS munkalapon a mért nyomást, a cserélt alkatrészeket és a felhasznált olaj mennyiségét.</li>
</ol>

<h2>5. Szükséges szerszámok és anyagok</h2>
<ul>
<li>Ellenőrző manométer 0–10 bar, mérőcsonk-adapter M10x1</li>
<li>Villáskulcs-készlet 10–24 mm, imbuszkulcs-készlet</li>
<li>Olajfelfogó tálca (min. 25 l), itatós kendő</li>
<li>ATF (Dexron III) olaj, szűrőbetét NSZ-10-JR, szívószűrő KS-150-JR</li>
</ul>

<h2>6. Felelősök</h2>
<p>Az olajszint napi ellenőrzése és utántöltése: <b>operátor</b>. Szűrőcsere, szivattyú- és szelepjavítás: <b>karbantartó</b>.
Ha a hiba 2 órán belül nem hárítható el, értesíteni kell a műszakvezetőt.</p>
""",
    ),
    "MWI-90102_SG40_Sorjazo_Levegoelokeszito_csere.pdf": (
        "MWI-90102 – SG-40 sorjázó gép: levegőelőkészítő egység (FRL) cseréje",
        """
<p><b>Dokumentum azonosító:</b> MWI-90102 &nbsp; <b>Verzió:</b> 1 &nbsp; <b>Hatályos:</b> 2025.06.15.<br/>
<b>Részleg:</b> Sorjázás és mosás &nbsp; <b>Gép:</b> SG-40 kefés sorjázó gép<br/>
<b>Érintett gépszámok:</b> #268, #270</p>

<h2>1. Cél</h2>
<p>A sorjázó gép pneumatikus rendszerét ellátó levegőelőkészítő egység (szűrő–nyomásszabályzó–olajozó, FRL)
cseréje. Cserét kell végezni, ha a szabályzó nem tartja a nyomást, a szűrőház repedt, a kondenzátum-leeresztő
tartósan szivárog, vagy a „PNEUMATIKA NYOMÁS ALACSONY” (P-07) hiba ismétlődik.</p>

<h2>2. Szükséges gépek, eszközök és alkatrészek</h2>
<table>
<tr><th>Megnevezés</th><th>Cikkszám</th><th>Mennyiség</th></tr>
<tr><td>Levegőelőkészítő egység, G1/2", 5 µm szűrő, manométerrel</td><td>FRL-12-5-SG</td><td>1 db</td></tr>
<tr><td>Gyorscsatlakozó, egyenes, 12 mm cső</td><td>GYC-12-G12</td><td>2 db</td></tr>
<tr><td>Fali tartókonzol FRL egységhez</td><td>TK-FRL-12</td><td>1 db</td></tr>
<tr><td>Menettömítő szalag (PTFE)</td><td>PTFE-12</td><td>1 tekercs</td></tr>
<tr><td>Pneumatika olaj, ISO VG 32 (olajozóhoz)</td><td>PO-32</td><td>0,1 l</td></tr>
</table>
<p><b>Szerszámok:</b> villáskulcs 24 mm és 27 mm, csőcsavarkulcs, imbuszkulcs-készlet, csővágó 12 mm-es csőhöz,
szivárgáskereső spray. <b>Egyéni védőeszköz:</b> védőszemüveg, kesztyű.</p>

<h2>3. Előkészítés</h2>
<ol>
<li>Egyeztessen a műszakvezetővel: a gép a csere idejére (kb. 45 perc) leáll.</li>
<li>Végezze el az energiamentesítést a BIZ-001 szerint. A pneumatikus főelzáró golyóscsapot zárja el és lakatolja le.</li>
<li>A maradék nyomást a FRL egység leeresztő szelepén engedje le, a manométernek 0 bar-t kell mutatnia.</li>
</ol>

<h2>4. A csere lépései</h2>
<ol>
<li>Bontsa a be- és kimeneti csőcsatlakozásokat. Jelölje meg a csöveket.</li>
<li>Szerelje le a régi egységet a tartókonzolról.</li>
<li>Az új egység menetes csatlakozóira tekerjen PTFE szalagot (3–4 menet, a menetiránnyal megegyezően).</li>
<li>Szerelje fel az új egységet. Figyeljen az áramlási irányra (nyíl a házon)! A szűrőpohár lefelé álljon.</li>
<li>Csatlakoztassa a csöveket, és töltse fel az olajozót ISO VG 32 pneumatika olajjal a jelölésig.</li>
<li>Nyissa a főelzárót lassan, és állítsa a nyomásszabályzót <b>6,0 bar</b> értékre, majd rögzítse a beállítógombot.</li>
<li>Az olajozó adagolását állítsa 1 csepp / 10 munkaciklus értékre.</li>
<li>Szivárgáskereső spray-vel ellenőrizze az összes csatlakozást.</li>
</ol>

<h2>5. Átadás</h2>
<p>Futtasson 10 sorjázási ciklust üresen. A nyomás terhelés alatt sem eshet 5,5 bar alá. Rögzítse a CMMS-ben a
beállított nyomást és a felhasznált alkatrészeket, majd adja át a gépet az operátornak.</p>
<p><b>Megelőző karbantartás:</b> a szűrőbetétet (cikkszám: SZB-5-12) negyedévente kell cserélni, a kondenzátumot
műszakonként le kell ereszteni (operátor feladata).</p>
""",
    ),
    "MWI-90103_HP160_Hidraulikus_pres_olaj_es_szurocsere.pdf": (
        "MWI-90103 – HP-160 hidraulikus prés: olaj- és szűrőcsere, olajhőmérséklet-hiba",
        """
<p><b>Dokumentum azonosító:</b> MWI-90103 &nbsp; <b>Verzió:</b> 2 &nbsp; <b>Hatályos:</b> 2025.01.10.<br/>
<b>Részleg:</b> Szerelés &nbsp; <b>Gép:</b> HP-160 hidraulikus prés (160 t) &nbsp; <b>Gépszám:</b> #400</p>

<h2>1. Műszaki adatok</h2>
<ul>
<li>Hidraulikaolaj: <b>HLP 46</b>, tartálytérfogat: <b>160 l</b></li>
<li>Rendszernyomás: max. 210 bar, munkanyomás: 180 bar</li>
<li>Visszatérő ági szűrő: 10 µm, cikkszám: HSZ-10-160; levegőztető szűrő: LSZ-HP-01</li>
<li>Olajhőmérséklet: üzemi 35–55 °C; <b>60 °C</b> felett figyelmeztetés (H-12), <b>70 °C</b> felett a prés leáll (H-13)</li>
<li>Olajhűtő: víz-olaj hőcserélő, hűtővíz a CH-200 hűtőből (#905)</li>
</ul>

<h2>2. Időszakos olaj- és szűrőcsere</h2>
<p><b>Intervallum:</b> szűrőcsere 6 havonta vagy ha az eltömődés-jelző piros; olajcsere 4000 üzemóránként vagy évente,
illetve ha az olajminta-vizsgálat szerint szükséges.</p>
<ol>
<li>Energiamentesítés a BIZ-001 szerint. A felső szerszámot alsó helyzetbe kell engedni, vagy ki kell támasztani!</li>
<li>Várja meg, amíg az olaj 40 °C alá hűl.</li>
<li>Engedje le az olajat a tartály leeresztőcsavarján keresztül (160 l, megfelelő gyűjtőedénybe).</li>
<li>Tisztítsa ki a tartályt szöszmentes kendővel, ellenőrizze a szívókosarat.</li>
<li>Cserélje a visszatérő ági szűrőbetétet (HSZ-10-160) és a levegőztető szűrőt (LSZ-HP-01).</li>
<li>Töltse fel a tartályt szűrőkocsin keresztül (10 µm) új HLP 46 olajjal a szintjelző felső jeléig.</li>
<li>Légtelenítés: járassa a szivattyút terhelés nélkül 5 percig, majd mozgassa a hengert 5-ször teljes löketen.</li>
<li>Ellenőrizze a szintet, szükség szerint töltsön utána.</li>
</ol>

<h2>3. „OLAJHŐMÉRSÉKLET MAGAS” (H-12 / H-13) hiba okai</h2>
<table>
<tr><th>Ok</th><th>Ellenőrzés / intézkedés</th></tr>
<tr><td>Nincs vagy kevés a hűtővíz</td><td>CH-200 hűtő (#905) működése, hűtővíz-szelep nyitva, átfolyás min. 25 l/perc</td></tr>
<tr><td>Elszennyeződött hőcserélő</td><td>Vízoldali vízkőmentesítés, nyomásesés ellenőrzése</td></tr>
<tr><td>Alacsony olajszint</td><td>Utántöltés HLP 46 olajjal, szivárgás keresése</td></tr>
<tr><td>Nyomáshatároló szelep folyamatosan nyit</td><td>Beállítás ellenőrzése (210 bar), szelep tisztítása/cseréje</td></tr>
<tr><td>Belső szivárgás (kopott szivattyú, henger tömítés)</td><td>Résolaj mérése, tömítéscsere</td></tr>
<tr><td>Hibás hőmérséklet-érzékelő (PT100)</td><td>Ellenállás mérése: 20 °C-on kb. 108 Ω</td></tr>
</table>

<h2>4. Biztonság</h2>
<p>Nyomás alatt álló hidraulikus rendszeren bontani TILOS. Bontás előtt a nyomástárolót le kell üríteni, a manométernek
0 bar-t kell mutatnia. A forró olaj égési sérülést okozhat.</p>
""",
    ),
    "MWI-90104_KS55_Csavarkompresszor_karbantartas_hibakodok.pdf": (
        "MWI-90104 – KS-55 csavarkompresszor: karbantartás és hibakódok",
        """
<p><b>Dokumentum azonosító:</b> MWI-90104 &nbsp; <b>Verzió:</b> 2 &nbsp; <b>Hatályos:</b> 2025.02.20.<br/>
<b>Részleg:</b> Közműellátás &nbsp; <b>Gép:</b> KS-55 olajkenésű csavarkompresszor (55 kW) &nbsp; <b>Gépszám:</b> #900</p>

<h2>1. Műszaki adatok</h2>
<ul>
<li>Hálózati nyomás: 7,0 bar (terhelés 6,5 bar-nál, leterhelés 7,5 bar-nál)</li>
<li>Kompresszorolaj: KO-46 szintetikus, töltet: 18 l</li>
<li>Megengedett csavarblokk-kilépő hőmérséklet: max. 100 °C, leállás 110 °C-on</li>
<li>Szűrők: levegőszűrő LSZ-55, olajszűrő OSZ-55, olajleválasztó betét OLB-55</li>
</ul>

<h2>2. Karbantartási ütemterv</h2>
<table>
<tr><th>Tevékenység</th><th>Intervallum</th><th>Felelős</th></tr>
<tr><td>Olajszint ellenőrzése, kondenzátum-leeresztő működése</td><td>Naponta</td><td>Közmű karbantartó</td></tr>
<tr><td>Hűtő (léghűtéses olajhűtő) tisztítása sűrített levegővel</td><td>Havonta</td><td>Karbantartó</td></tr>
<tr><td>Levegőszűrő csere (LSZ-55)</td><td>2000 üzemóra</td><td>Karbantartó</td></tr>
<tr><td>Olajszűrő (OSZ-55) és olajcsere</td><td>4000 üzemóra</td><td>Karbantartó</td></tr>
<tr><td>Olajleválasztó betét csere (OLB-55)</td><td>8000 üzemóra</td><td>Karbantartó</td></tr>
<tr><td>Biztonsági szelep ellenőrzése</td><td>Évente</td><td>Karbantartó</td></tr>
</table>

<h2>3. Hibakódok</h2>
<table>
<tr><th>Kód</th><th>Üzenet</th><th>Lehetséges ok</th><th>Teendő</th></tr>
<tr><td>E01</td><td>Motorvédelem kioldott</td><td>Túlterhelés, fázishiány</td><td>Hőrelé visszaállítása, áramfelvétel mérése</td></tr>
<tr><td>E02</td><td>Fázissorrend hiba</td><td>Hálózati beavatkozás után felcserélt fázisok</td><td>Villanyszerelő értesítése</td></tr>
<tr><td>E04</td><td>Csavarblokk hőmérséklet magas</td><td>Elszennyeződött hűtő, alacsony olajszint, hibás termosztátszelep, magas helyiséghőmérséklet</td><td>Hűtő tisztítása, olaj utántöltése, termosztátszelep ellenőrzése, kompresszorház szellőzése</td></tr>
<tr><td>E05</td><td>Hálózati nyomás magas</td><td>Hibás nyomástávadó, beragadt szívószelep</td><td>Távadó ellenőrzése, szívószelep tisztítása</td></tr>
<tr><td>E07</td><td>Olajleválasztó nyomásesés magas</td><td>Eltömődött olajleválasztó betét</td><td>OLB-55 csere</td></tr>
<tr><td>E09</td><td>Levegőszűrő eltömődött</td><td>Poros környezet, lejárt csereidő</td><td>LSZ-55 csere</td></tr>
<tr><td>E12</td><td>Kondenzátum-leeresztő hiba</td><td>Eltömődött leeresztő szelep</td><td>Szelep tisztítása, mágnestekercs ellenőrzése</td></tr>
</table>

<h2>4. Teendő E04 (túlmelegedés) esetén</h2>
<ol>
<li>A kompresszor automatikusan leáll. A tartalék kompresszort (#901) indítsa el kézzel, hogy a hálózati nyomás ne essen 6 bar alá.</li>
<li>Várjon legalább 15 percet, ne indítsa újra azonnal.</li>
<li>Ellenőrizze az olajszintet nyugalmi állapotban (szintüveg közepe).</li>
<li>Energiamentesítés után tisztítsa a hűtőt belülről kifelé fújva.</li>
<li>Ellenőrizze a hűtőventilátor forgásirányát és a kompresszorház szellőzőnyílásait.</li>
<li>Újraindítás után 30 percig figyelje a csavarblokk hőmérsékletét (normál: 75–90 °C).</li>
</ol>
""",
    ),
    "MWI-90105_Huto-keno_folyadek_kezelese.pdf": (
        "MWI-90105 – Hűtő-kenő folyadék (emulzió) kezelése a forgácsoló gépeken",
        """
<p><b>Dokumentum azonosító:</b> MWI-90105 &nbsp; <b>Verzió:</b> 4 &nbsp; <b>Hatályos:</b> 2025.04.01.<br/>
<b>Részleg:</b> Forgácsolás (Machining) &nbsp; <b>Gépek:</b> JR20/20 eszterga (#100, #105, #200), VMC-850 megmunkáló központ (#110, #115)</p>

<h2>1. Határértékek</h2>
<table>
<tr><th>Jellemző</th><th>Megengedett tartomány</th><th>Mérés módja</th><th>Gyakoriság</th></tr>
<tr><td>Koncentráció</td><td>6–8 %</td><td>Kézi refraktométer (Brix-érték × 1,1 korrekciós tényező)</td><td>Műszakonként</td></tr>
<tr><td>pH-érték</td><td>8,5–9,3</td><td>pH-mérő csík</td><td>Hetente</td></tr>
<tr><td>Szag, szín</td><td>Nincs záptojásszag, nincs elszíneződés</td><td>Érzékszervi</td><td>Műszakonként</td></tr>
<tr><td>Idegen olaj a felszínen</td><td>Max. 2 % / látható olajréteg nincs</td><td>Szemrevételezés</td><td>Naponta</td></tr>
</table>

<h2>2. Utántöltés</h2>
<ul>
<li>Alacsony koncentráció (6 % alatt): 2 %-os helyett 8 %-os előkevert emulzióval töltsön utána.</li>
<li>Magas koncentráció (8 % felett): tiszta vízzel töltsön utána. Koncentrátumot közvetlenül a tartályba önteni TILOS.</li>
<li>Mindig a koncentrátumot öntse a vízbe (és ne fordítva), a keverőállomáson.</li>
</ul>

<h2>3. Teljes csere</h2>
<p>Teljes cserét kell végezni, ha a pH 8,0 alá esik, bakteriális fertőzés (szag) jelentkezik, vagy legkésőbb 6 havonta.</p>
<ol>
<li>A régi emulziót szivattyúzza át a veszélyes hulladék gyűjtőtartályba.</li>
<li>Távolítsa el a forgácsot és az iszapot a tartályból.</li>
<li>Rendszertisztítóval (RT-200, 1 %) töltse fel a rendszert, és járassa 8 órán át.</li>
<li>Ürítse le, öblítse át tiszta vízzel.</li>
<li>Töltse fel 7 %-os friss emulzióval (VMC-850: 300 l, JR20/20: 180 l).</li>
<li>Rögzítse a CMMS-ben: dátum, mennyiség, mért koncentráció és pH.</li>
</ol>

<h2>4. Gyakori hibák</h2>
<ul>
<li><b>Habzás:</b> túl lágy víz vagy túl magas koncentráció — ellenőrizze a koncentrációt, szükség esetén habzásgátló (HG-5) adagolása.</li>
<li><b>Korrózió a munkadarabon:</b> alacsony koncentráció vagy alacsony pH.</li>
<li><b>Bőrirritáció:</b> túl magas koncentráció; használjon védőkesztyűt és bőrvédő krémet.</li>
<li><b>Hűtőfolyadék-szivattyú nem szállít („COOLANT FLOW LOW”, 3015-ös riasztás):</b> alacsony szint, eltömődött szívókosár vagy forgácsszűrő.</li>
</ul>
""",
    ),
    "BIZ-001_Energiamentesitesi_eljaras_LOTO.pdf": (
        "BIZ-001 – Energiamentesítési eljárás (LOTO – lakatolás és címkézés)",
        """
<p><b>Dokumentum azonosító:</b> BIZ-001 &nbsp; <b>Verzió:</b> 5 &nbsp; <b>Hatályos:</b> 2024.11.01.<br/>
<b>Érvényességi kör:</b> a Mintaüzem összes gépe és berendezése</p>

<h2>1. Cél</h2>
<p>Karbantartási, javítási és tisztítási munkák előtt minden veszélyes energiaforrást le kell választani és biztosítani kell
a véletlen visszakapcsolás ellen. Energiaforrások: villamos, pneumatikus, hidraulikus, mechanikai (rugó, gravitáció), termikus.</p>

<h2>2. Az energiamentesítés 8 lépése</h2>
<ol>
<li><b>Felkészülés:</b> azonosítsa a gép összes energiaforrását a gép LOTO-lapja alapján.</li>
<li><b>Értesítés:</b> tájékoztassa az operátort és a műszakvezetőt a leállásról.</li>
<li><b>Leállítás:</b> a gépet a normál leállítási móddal állítsa le.</li>
<li><b>Leválasztás:</b> kapcsolja le a főkapcsolót, zárja el a pneumatikus és hidraulikus elzárókat.</li>
<li><b>Lakatolás és címkézés:</b> minden leválasztó eszközre helyezze fel a saját személyes lakatját és a kitöltött címkét (név, dátum, telefonszám).</li>
<li><b>Tárolt energia levezetése:</b> engedje le a pneumatikus és hidraulikus nyomást, ürítse a nyomástárolókat, támassza ki a gravitációs terhelést.</li>
<li><b>Ellenőrzés:</b> próbálja meg elindítani a gépet (a startgomb nem indíthatja), feszültségmentességet mérjen, a manométerek 0 bar-t mutassanak.</li>
<li><b>Munkavégzés</b> csak sikeres ellenőrzés után kezdhető.</li>
</ol>

<h2>3. Visszakapcsolás</h2>
<ol>
<li>Szerszámok, anyagok eltávolítása, védőburkolatok visszaszerelése.</li>
<li>Személyek kiküldése a veszélyes zónából.</li>
<li>Lakatok és címkék eltávolítása — mindenki csak a saját lakatját veheti le.</li>
<li>Energiaforrások visszakapcsolása, próbaüzem, átadás az operátornak.</li>
</ol>

<h2>4. Csoportos lakatolás</h2>
<p>Ha több karbantartó dolgozik egy gépen, csoportos lakatolódobozt kell használni. Minden résztvevő a saját lakatját helyezi a dobozra.
A gép csak akkor kapcsolható vissza, ha az utolsó lakatot is eltávolították.</p>
""",
    ),
    "MWI-90106_VMC850_Szerszamcserelo_ATC_hibak.pdf": (
        "MWI-90106 – VMC-850 megmunkáló központ: szerszámcserélő (ATC) hibák elhárítása",
        """
<p><b>Dokumentum azonosító:</b> MWI-90106 &nbsp; <b>Verzió:</b> 1 &nbsp; <b>Hatályos:</b> 2025.05.12.<br/>
<b>Részleg:</b> Forgácsolás (Machining) &nbsp; <b>Gép:</b> VMC-850 függőleges megmunkáló központ<br/>
<b>Érintett gépszámok:</b> #110, #115</p>

<h2>1. A szerszámcserélő felépítése</h2>
<p>24 helyes tárcsás szerszámtár, kettős megfogókar, BT40 kúp. A szerszámbefogás tányérrugó-köteggel, az oldás pneumatikus-hidraulikus
erősítővel (6 bar bemenő levegőnyomás) történik. A főorsó-orientáció helyzetét a cserekarhoz a 4071-es paraméter tárolja.</p>

<h2>2. Riasztások</h2>
<table>
<tr><th>Riasztás</th><th>Üzenet</th><th>Lehetséges ok</th><th>Teendő</th></tr>
<tr><td>2310</td><td>ATC kar nem érte el a végállást</td><td>Elszennyeződött / elállítódott közelítéskapcsoló, kopott kar-hajtás</td><td>Kapcsoló tisztítása, távolság beállítása (1,5 mm)</td></tr>
<tr><td>2315</td><td>Szerszám oldás nem történt meg</td><td>Alacsony levegőnyomás, hibás mágnesszelep, kevés olaj az erősítőben</td><td>Nyomás ellenőrzése (min. 5,5 bar), erősítő olajszintje, szelep</td></tr>
<tr><td>2320</td><td>Szerszámtár pozíció hiba</td><td>Elcsúszott tár-számlálás, hibás jeladó</td><td>Tár referenciafelvétele (MDI: M190), jeladó ellenőrzése</td></tr>
<tr><td>2331</td><td>Szerszám nincs megfogva</td><td>Gyenge tányérrugó, szennyezett kúp, rossz behúzócsap</td><td>Befogóerő mérése (min. 8 kN), kúp tisztítása</td></tr>
</table>

<h2>3. Elakadt szerszámcsere utáni helyreállítás</h2>
<ol>
<li>Nyomja meg a RESET gombot, és kapcsoljon kézi (JOG) üzemmódba.</li>
<li>Kapcsolja a gépet „ATC karbantartás” módba (kulcsos kapcsoló 2-es állás).</li>
<li>A kart a kézi tárcsával lassan forgassa vissza alaphelyzetbe. Ellenőrizze, hogy a szerszám nem esik ki a karból!</li>
<li>Ha szerszám maradt a karban, támassza alá és nyomja meg a kézi oldógombot.</li>
<li>Végezze el a tár referenciafelvételét (M190), majd ellenőrizze a szerszámtáblázatot.</li>
<li>Futtasson 10 próba-szerszámcserét (M06) üres orsóval, majd 10-et szerszámmal.</li>
</ol>

<h2>4. Megelőző karbantartás</h2>
<ul>
<li>Hetente: főorsókúp és megfogókar pofáinak tisztítása, levegő-tisztítófúvás ellenőrzése.</li>
<li>Havonta: az erősítő olajszintjének ellenőrzése, közelítéskapcsolók tisztítása.</li>
<li>Félévente: befogóerő mérése befogóerő-mérővel (névleges 10 kN, min. 8 kN).</li>
</ul>
""",
    ),
    "MWI-90107_R6_Robotcella_utkozes_utani_ujrainditas.pdf": (
        "MWI-90107 – R-6 robotcella: ütközés utáni ellenőrzés és újraindítás",
        """
<p><b>Dokumentum azonosító:</b> MWI-90107 &nbsp; <b>Verzió:</b> 2 &nbsp; <b>Hatályos:</b> 2025.08.04.<br/>
<b>Részleg:</b> Szerelés &nbsp; <b>Gép:</b> R-6 hattengelyes robot szerelőcellában &nbsp; <b>Gépszám:</b> #300</p>

<h2>1. Cél</h2>
<p>Ütközésérzékelés (riasztás: <b>SRVO-050 „Ütközés észlelve”</b>) után a robot és a megfogó állapotának ellenőrzése,
illetve a cella biztonságos újraindítása.</p>

<h2>2. Azonnali teendők</h2>
<ol>
<li>Ne nyugtázza azonnal a hibát. Mérje fel a helyzetet: van-e személyi sérülés, sérült alkatrész, beszorult munkadarab.</li>
<li>A cellába csak a biztonsági ajtón keresztül, a reteszelt ajtó kulcsát magánál tartva lépjen be.</li>
<li>Fényképezze le a robot és a megfogó helyzetét (a hibaelemzéshez).</li>
</ol>

<h2>3. Kiszabadítás</h2>
<ol>
<li>Kézi programozó egységen (TP) válassza a T1 (csökkentett sebesség, max. 250 mm/s) módot.</li>
<li>Nyugtázza a riasztást (RESET), és tartsa lenyomva a jóváhagyó (deadman) kapcsolót.</li>
<li>A robotot világ- (WORLD) koordinátában, az ütközés irányával ellentétesen mozgassa el, legalább 50 mm-re.</li>
<li>Távolítsa el a beszorult vagy sérült munkadarabot.</li>
</ol>

<h2>4. Ellenőrzések újraindítás előtt</h2>
<ul>
<li>A megfogó ujjak, érzékelők és pneumatikus csövek sérülésmentesek-e (megfogó nyomás: 5 bar).</li>
<li>A törésvédő (ütközésvédő) egység visszaállt-e alaphelyzetbe — jelzőlámpa zöld.</li>
<li>Referenciapont-ellenőrzés: a robotot a „REF_CHECK” programmal a kalibráló tüskére kell vinni. Megengedett eltérés: ±0,5 mm.
Nagyobb eltérés esetén a TCP (szerszám-középpont) újrakalibrálása szükséges, ezt csak robotprogramozó végezheti.</li>
<li>Kábelköteg és öltözet (dress pack) nem sérült-e.</li>
</ul>

<h2>5. Újraindítás</h2>
<p>Az első 3 ciklust T2 (teljes sebesség, felügyelt) módban kell futtatni, majd AUTO módba lehet kapcsolni.
Ha egy műszakon belül 2-nél több ütközés történik, értesíteni kell a robotprogramozót (a pályát felül kell vizsgálni).</p>
""",
    ),
}
