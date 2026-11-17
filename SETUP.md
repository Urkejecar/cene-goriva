# Putting "Cene goriv" on the internet (free)

The website lives on **GitHub** (free). GitHub also runs a small job every 30 minutes
that collects the newest prices and updates the website. You only do the steps
below once.

## 1. Create a free GitHub account

1. Go to <https://github.com/signup> and create an account (email + password).
2. Remember your **username**. It becomes part of the website address.

## 2. Create an empty project ("repository")

1. Go to <https://github.com/new>.
2. **Repository name:** `cene-goriva`
3. Choose **Public** (needed for free hosting; it only contains fuel prices).
4. Do **not** tick "Add a README" or anything else.
5. Click **Create repository**.

## 3. Turn on the website (before uploading)

1. In the new repository, open **Settings → Pages**.
2. Under **Build and deployment → Source**, choose **GitHub Actions**.

## 4. Upload the app

Tell Claude: "the repository is ready, my username is …". Claude runs:

```
git remote add origin https://github.com/<username>/cene-goriva.git
git push -u origin main
```

A browser window may open asking you to sign in to GitHub. Sign in and allow it.

## 5. Check that it worked

1. Open the **Actions** tab of the repository.
2. Wait 1–2 minutes until the run called **update** has a green tick.

Your website is now at:

**`https://<username>.github.io/cene-goriva/`**

Send this link to family and friends. After that it updates itself every 30 minutes.

## 6. Add it to the phone home screen (like an app)

- **Android (Chrome):** open the link → menu ⋮ → **Add to Home screen**.
- **iPhone (Safari):** open the link → Share button → **Add to Home Screen**.

## Emails from GitHub, and what to do

- **"Run failed: update"**: a price source has not worked for 3 hours (you get
  at most one such email per day per source). The website keeps showing the last good
  prices, and the affected country card shows a yellow note "Cena morda ni več aktualna".
  If it doesn't fix itself within a day, open Claude Code in this folder and say:
  *"the fuel price update is failing, please fix it"*.
- **"Scheduled workflow … will be disabled"**: GitHub pauses automatic jobs in
  repositories without activity for 60 days. Open **Actions → update** and click
  **Enable workflow** (or just run it once with **Run workflow**).

## For Claude (maintenance notes)

- The update job commits price data to `main` every day: always `git pull` before
  changing code.
- Tests: `python -m pytest -q` and `node --test site/logic.test.js`.
- Design and plan: `docs/superpowers/specs/` and `docs/superpowers/plans/`.
