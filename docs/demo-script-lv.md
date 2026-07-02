# KIRI-LV demo scenārijs sapulcei

Šis ir īsais runas scenārijs, ko var izmantot, demonstrējot web karti.

## 1. Atvēršana

Atveru KIRI-LV demonstrācijas lapu:

```text
https://dboka.github.io/KIRI/
```

“Šis ir kūtsmēslu izkliedes riska kartes prototips Latvijai. Tas apvieno nokrišņu datus, satelītu augsnes mitruma indikatorus un 1 km režģi, lai parādītu, kur izkliedei konkrētajā dienā ir zemāks vai augstāks risks.”

## 2. Latvijas pārskats

“Sākumā redzam pašvaldību pārskatu. Krāsa parāda dominējošo riska situāciju pašvaldībā. Riska līmenis ir no 1 līdz 5: zaļāks ir zemāks risks, oranžs/sarkans ir augstāks risks.”

## 3. Datuma izvēle

Atver datuma izvēlni.

“Šajā versijā ir sagatavotas 60 dienas no 2026-05-02 līdz 2026-06-30. Datumu var mainīt, un karte ielādē attiecīgās dienas risku.”

## 4. Pašvaldības atvēršana

Klikšķini uz pašvaldības.

“Klikšķinot uz pašvaldības, redzam detalizētu 1 km režģi. Tas ļauj skatīties ne tikai pašvaldības kopējo stāvokli, bet arī telpisko atšķirību pašvaldības iekšienē.”

## 5. Grid šūnas skaidrojums

Klikšķini uz konkrētas šūnas.

“Šeit redzam, kāpēc risks ir tāds: H-SAF virsmas mitrums, SWI, P30, P90 un P730. P30 ir pēdējo 30 dienu nokrišņi, P90 ir 90 dienu uzkrājums, P730 ir ilgtermiņa nokrišņu fons.”

## 6. Riska loģika

“Modelis ir moisture-first. Tas nozīmē, ka vispirms skatāmies faktisko mitruma situāciju, īpaši H-SAF virsmas mitrumu. Nokrišņi palīdz saprast īstermiņa un ilgtermiņa fonu. P730 nav tiešs aizliegums, bet konteksta modifikators.”

## 7. Arhitektūras ieguvums

“v0.1.2 versijā sakārtojām datu arhitektūru: 1 km grid ģeometrija tiek glabāta vienu reizi, un katrai dienai pievienojam tikai vērtības. Tas ir svarīgi ātrdarbībai un nākamajam solim - automātiskai dienu pievienošanai.”

## 8. Godīgais ierobežojumu skaidrojums

“Šis vēl nav juridiskais lēmumu dzinējs. Normatīvie hard-stop nosacījumi vēl nav pieslēgti. Šis ir operatīvs riska indikators, ko var kalibrēt ar ekspertiem un papildināt ar juridiskajiem slāņiem.”

## 9. Noslēgums

“Mērķis ir panākt, lai katru dienu automātiski ienāk jaunākie dati, tiek pārrēķināts risks un web karte publicējas bez manuālas ģeometrijas ģenerēšanas. Šī versija ir sagatavota tieši šim nākamajam solim.”
