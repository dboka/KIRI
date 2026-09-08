# Runas teksts ZM sapulcei par KIRI-LV pilotu

## 1. Ievads

Šodien gribu īsi parādīt, ko esmu jau apkopojis kūtsmēslu izkliedes riska projekta pilotam. Šis vēl nav gala normatīvais instruments. Tas ir pirmais strādājošais prototips, kur var redzēt datu ķēdi no satelītiem un nokrišņiem līdz kartei.

Mans mērķis sapulcē ir parādīt trīs lietas: kādi dati ir pieejami, kā tie tiek apstrādāti vienotā režģī un kā pilots jau darbojas saitē.

## 2. Kas jau ir apkopots

Darba plāna satelītu daļai esmu piesaistījis H-SAF virsmas augsnes mitrumu, Copernicus Soil Water Index un CLIDATA nokrišņu indikatorus. Pilotā tie tiek pārveidoti par vienotu 1 km režģi Latvijai.

Pašreizējais rīks rāda 60 dienu datu logu, 43 pašvaldības un detalizētu grid skatu. Tas nozīmē, ka var sākt ar saprotamu Latvijas karti, bet, ja vajag, atvērt konkrētu pašvaldību un skatīties šūnu līmenī.

## 3. Darba plāna sasaite

Darba plāna 2.1 punkts prasa iegūt un analizēt SSM un SWI datus. Tas pilotā jau ir ielikts kā datu avotu bloks.

2.2 prasa telpisku pārklājumu. To pilots risina ar 1 km režģi, pašvaldību pārskatu un dienas datu manifestiem.

2.3 prasa satelītu un staciju datu integrāciju. Te vēl vajag pilnu staciju datu pieslēgumu, bet datu modelis jau paredz salīdzinājumu ar tuvāko vai 3x3 grid šūnu apkārtni.

2.4 un 4.1 jau redzami pilotā: ir riska līmenis 1-5, iemeslu kodi, pārliecības līmenis un karšu rīks.

## 4. Datu avoti

Pirmajai versijai pietiek ar pieciem indikatoriem: P30, P90, P730, H-SAF SSM un Copernicus SWI.

P30 rāda īstermiņa slapjuma fonu. P90 dod sezonālāku kontekstu. P730 rāda ilgāku hidroloģisko fonu.

H-SAF SSM dod virsmas slāņa mitruma signālu. Copernicus SWI dod profila mitruma dinamiku Eiropas 1 km ikdienas produktā. Staciju dati vajadzīgi, lai šo satelītu signālu pārbaudītu Latvijas apstākļos.

## 5. Kā dati kļūst par karti

Tehniski process ir šāds: dati tiek iegūti no avotiem, izgriezti Latvijai, piesaistīti 1 km režģim, pārvērsti indikatoros un pēc tam publicēti kartē.

Svarīgi, ka tā nav vienreizēja bilde. Tā ir reproducējama datu ķēde. Frontend glabā statisko grid ģeometriju vienreiz, bet katrai dienai ielādē tikai vērtības. Tas ļauj turēt rīku ātru un uzturamu.

## 6. 60 dienu riska signāls

No esošā datu loga var iegūt arī dinamiku. Piemēram, jaunākajā datumā 2026-09-06 redzamajās šūnās 93 procenti ir 4. vai 5. riska līmenī pēc pašreizējās pilotmetodikas.

Te es uzsveru: tas nav juridisks aizliegums. Tas ir hidroloģiskā un mitruma riska signāls. Ja jaunākajai dienai kāds satelīta avots kavējas, rīks to parāda ar pārliecības līmeni.

## 7. Saites demonstrācija

Demonstrācijā atveru: https://dboka.github.io/KIRI/

Sākumā parādu Latvijas pašvaldību karti. Augšā ir aktīvais datums. Datuma panelī var izvēlēties vienu no 60 dienām. Leģenda rāda 1-5 riska līmeņus.

Svarīgākais ir parādīt, ka lietotājs uzreiz redz kopējo situāciju Latvijā.

## 8. Pašvaldības grid skats

Pēc tam klikšķinu uz pašvaldības. Karte pāriet uz 1 km grid skatu. Panelī redzams kopējais risks, augsta riska šūnu īpatsvars, dominējošie faktori un rekomendācija.

Klikšķis uz grid šūnas parāda konkrētos indikatorus. Šis ir svarīgs arguments, jo pašvaldības krāsa nav melnā kaste. Aiz tās ir pārbaudāmas šūnas un iemeslu kodi.

## 9. Pašreizējais algoritms

Pilotā katrs indikators tiek pārvērsts 1-5 riska līmenī. Kopējais risks tiek aprēķināts ar moisture-first pieeju. Rezultātam līdzi nāk aktīvie iemesli un datu pārliecības līmenis.

Šobrīd es nesaku, ka sliekšņi ir galīgi. Tie ir darba sliekšņi pilotam. Nākamais zinātniskais solis ir robežvērtību kalibrēšana pret vēsturiskajiem datiem, staciju mērījumiem un LBTU novērojumiem.

## 10. Satelītdatu kvalitāte

Lai satelītdatus varētu aizstāvēt, vajag validāciju. To var darīt divos līmeņos.

Pirmais līmenis ir satelīts pret staciju: tuvākā grid šūna vai 3x3 grid apkārtne pret augsnes mitruma un temperatūras sensoru.

Otrais līmenis ir riska indekss pret reālām N/P zudumu epizodēm un hidroloģiskajiem apstākļiem. Te LBTU dati ir ļoti svarīgi.

## 11. Ko prasīt no ZM

Sapulces noslēgumā es prasītu nofiksēt piecus jautājumus.

Pirmkārt, kuras robežvērtības jāvalidē pirmajā posmā. Otrkārt, kā tiks nodrošināta piekļuve augsnes mitruma un temperatūras staciju datiem. Treškārt, kuri normatīvie hard-stop noteikumi jāievieš kā atsevišķs slānis.

Ceturtkārt, kāds ir minimālais pilots nākamajam starpposmam. Piektkārt, kā sadalīt lomas starp LVĢMC, ZM un LBTU.

## 12. Noslēgums

Mans piedāvājums ir turpināt no šī prototipa, nevis sākt no nulles. Datu ķēde jau ir pārbaudāma, karte jau darbojas un nākamais vajadzīgais solis ir metodikas validācija.

Sapulces praktiskais rezultāts varētu būt vienošanās par validācijas protokolu un robežvērtību darba grupu.
