# KIRI darba plūsma: `main` un eksperimentālie zari

## Zaru lomas

| Zars | Mērķis | GitHub Pages |
| --- | --- | --- |
| `main` | Stabilā, publicējamā KIRI versija | Jā — publicējas pēc `push` uz `main` |
| `codex/experimental-dem-grid-27105` | 1 m DEM pilota izstrāde šūnai 27105 | Nē |

`.github/workflows/pages.yml` klausās tikai `main`. Tāpēc eksperimentālā zara
`push` saglabā kodu GitHub, bet nemaina publisko KIRI versiju.

## Viena repozitorija mape: pārslēgšanās starp zariem

Pirms pārslēgšanās izmaiņas ir jāiekomitē vai jāieliek `stash`.

Darbs stabilajā versijā:

```powershell
git switch main
git pull --ff-only origin main
git branch --show-current
```

Darbs DEM eksperimentā:

```powershell
git switch codex/experimental-dem-grid-27105
git pull --ff-only
git branch --show-current
```

Eksperimenta izmaiņu saglabāšana:

```powershell
git status
git add <konkrēti-faili-vai-mapes>
git commit -m "Apraksts par eksperimenta izmaiņām"
git push
```

Nelietot `git add .`, ja mapē ir lieli neapstrādāti LiDAR/LAS faili. Pirms
`commit` vienmēr pārbaudīt `git status` un `git diff --cached --stat`.

## Divas darba mapes vienlaikus (`git worktree`)

Ja stabilā un eksperimentālā versija jāatver reizē, pašreizējo `KIRI` mapi var
atstāt uz eksperimentālā zara un blakus izveidot stabilās versijas mapi:

```powershell
git -C C:\Users\deniss.boka\MESLI_PROJECT\KIRI branch --show-current
git -C C:\Users\deniss.boka\MESLI_PROJECT\KIRI worktree add C:\Users\deniss.boka\MESLI_PROJECT\KIRI-main main
```

Tad:

- `C:\Users\deniss.boka\MESLI_PROJECT\KIRI` ir DEM eksperiments;
- `C:\Users\deniss.boka\MESLI_PROJECT\KIRI-main` ir stabilais `main`.

Katrā mapē izpilda `git status` un `git push` neatkarīgi. Vienu un to pašu zaru
Git neļauj vienlaikus piesaistīt divām worktree mapēm.

## Jaunākā `main` koda ienešana eksperimentā

```powershell
git switch codex/experimental-dem-grid-27105
git fetch origin
git merge origin/main
git push
```

Tas atjaunina eksperimentu, nemainot `main`.

## Eksperimenta nodošana uz `main`

Kad pilots ir pārbaudīts, GitHub izveido Pull Request no
`codex/experimental-dem-grid-27105` uz `main`. Kamēr Pull Request nav sapludināts,
publiskā versija nemainās. Pirms merge jāpārbauda, ka nav pievienoti neapstrādāti
LAS faili un ka DEM funkcija korekti strādā arī bez `?grid=27105` parametra.

## Commit identitāte

Šim repozitorijam lokāli ir iestatīts:

```text
user.name  = Deniss Boka
user.email = 210702039+dboka@users.noreply.github.com
```

Tā ir GitHub noreply adrese, kas piesaista commitus lietotājam `dboka`,
nepubliskojot privāto e-pasta adresi.
