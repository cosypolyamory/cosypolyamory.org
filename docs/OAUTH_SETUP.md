# Setup Oauth Identification

This guide is for logging in the NewCosy website.
So far only instructions for the Google way are present.

## Google OAUTH Instructions

### 1. Find the instructions page

at the time of writing, this guide is the correct one:
> Manage OAuth Clients
> https://support.google.com/cloud/answer/15549257

### 2. Access Google's Developer Console

https://console.developers.google.com/auth/clients

You may be prompted to create a project if you do not have one selected.
2.1 Click on `Create Project`
2.2 Fill the `Project name` and the `Location` (doesn't really matter but has to be present)
2.3 Click on `Create`

### 3. Configure the App on Google's Developer Console

3.1 Click on `Get Started`

> App Information
3.2 Fill the `App name` (can be what you want) and the `User support email`
3.3 Click `Next`

> Audience
3.4 Select `External` and click on `Next`

> Contact Information
3.5 Fill out the `Email Address` and click on `Next`

> Finish
3.6 Check the `I agree` checkbox
3.7 Click on `Continue` and then on `Create`

### 4. Create OAuth client

4.1 From the top navbar select the correct project (the name chosen in step 2.2)
4.2 Go to Overview (https://console.cloud.google.com/auth/overview)

4.3 Click on `Create OAuth client`
4.4 Select `Web application` on `Application type`
4.5 Fill the `name` (can be creative)

4.6 Under `Authorised redirect URIs`, click on `+ Add URI` (this is very important)
4.7 Fill the `URI` with `http://127.0.0.1:5000/callback/google` (or the address of your local server)
4.8 Click on `Create`

4.9 If prompted, copy somewhere the `Client ID` and the `Secret` and click on `Ok`

### 5. Copy Credentials to the local Cosy App
5.1 From https://console.cloud.google.com/auth/clients double click on the name of the correct `Client`
5.2 Copy the `Client ID` and the `Secret`
5.3 If the `Secret` is not available, click on `+ Add Secret` and copy it

5.3 In your hard disk, in the Cosy project folder, copy the file `.env.example` and rename it to `.env`
5.4 Open `.env` with a *simple text editor* (like notepad, but NOT LIKE WORD)

5.5 In `.env`, fill up these two fields under `# OAuth Configuration`: `GOOGLE_CLIENT_ID=` and `GOOGLE_CLIENT_SECRET=`

### 6. Login through the Cosy App
6.1 Restart the local server (`CTRL+C` from the console that is running it and then run it again)
6.2 In the Cosy App, throught the browser, click on `+Join Community` and then `Continue with Google`

6.3 SOMETIMES Google Auth Platform WILL TAKE A WHILE to update itself, so you may get weird errors

6.4 Profit! Now you can make yourself an admin, check the main Readme to see how!
