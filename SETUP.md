# Putting "Cene goriv" on the internet (free)

The website lives on **GitHub** (free). GitHub also runs a small job every 30 minutes
that collects the newest prices and updates the website. You only do the steps
below once.

## 1. Create a free GitHub account

1. Go to <https://github.com/signup> and create an account (email + password).
2. Remember your **username** — it becomes part of the website address.

## 2. Create an empty project ("repository")

1. Go to <https://github.com/new>.
2. **Repository name:** `cene-goriva`
3. Choose **Public** (needed for free hosting; it only contains fuel prices).
4. Do **not** tick "Add a README" or anything else.
5. Click **Create repository**.

## 3. Upload the app

Tell Claude: "the repository is ready, my username is …". Claude runs:

```
git remote add origin https://github.com/<username>/cene-goriva.git
git push -u origin main
```

A browser window may open asking you to sign in to GitHub — sign in and allow it.

## 4. Turn on the website

1. In your repository on GitHub, open **Settings → Pages**.
2. Under **Build and deployment → Source**, choose **GitHub Actions**.

## 5. Run it the first time

1. Open the **Actions** tab of the repository.
2. Click **update** on the left, then **Run workflow → Run workflow**.
3. Wait 1–2 minutes until the run has a green tick.

Your website is now at:

**`https://<username>.github.io/cene-goriva/`**

Send this link to family and friends. After that it updates itself every 30 minutes.

## 6. Add it to the phone home screen (like an app)

- **Android (Chrome):** open the link → menu ⋮ → **Add to Home screen**.
- **iPhone (Safari):** open the link → Share button → **Add to Home Screen**.

## If you get an email "Run failed: update"

One of the price sources changed its format or was down. The website keeps showing
the last good prices (and a yellow "Podatki morda niso sveži" note if it's more than
3 hours old). If the emails keep coming for more than a day, open Claude Code in this
folder and say: *"the fuel price update is failing, please fix it"*.
