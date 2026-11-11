# WhatsApp for the plant app

Customers who turn WhatsApp on get their plant app notifications on WhatsApp too: visits planned or moved, technician on the way, visit done and report ready, cleaning needed, replies to their requests, daily log reminders. Staff can also send a new person's invitation link by WhatsApp. It uses Meta's **WhatsApp Cloud API** (the WhatsApp Business Platform).

Nothing is sent until the set-up below is done and **Send WhatsApp Messages** is ticked.

## How it works

- **Customers agree first.** A customer turns WhatsApp on in the plant app (**Account → Notifications → WhatsApp**) by entering their number, which records their agreement and when. When inviting someone, staff may tick **Also send it by WhatsApp** only if the person agreed.
- **Business-started messages need approved templates.** WhatsApp only lets a business start a conversation with a template Meta has approved. Everything goes out as one of two templates: *update* (every notification) and *invitation*.
- **STOP.** Replying **STOP** switches WhatsApp off for that number. They can turn it back on in the app.
- **Message log.** Every message is kept in Desk as **Techy WhatsApp Message**, with the status WhatsApp reports (*Sent*, *Delivered*, *Read* or *Failed*) and the reason for a failure.
- **Preferences.** The customer's other choices still apply. With *Log reminders* off, there's no reminder on WhatsApp either.

## Set-up (once)

You need a Meta Business account and a phone number for WhatsApp. The number cannot also be used in the WhatsApp or WhatsApp Business phone app.

1. In **Meta for Developers**, create an app of type *Business* and add the **WhatsApp** product. Link it to your Meta Business account and add your business phone number. Meta verifies it by SMS or a call.
2. In **WhatsApp Manager → Message templates**, create the two templates below. Use category **Utility** and the same language for both (for example *English*). Wait for Meta to approve them; this usually takes minutes to a day.
3. In **Business Settings → System users**, create a system user and give it the app and your WhatsApp account. Generate a **permanent token** with the `whatsapp_business_messaging` and `whatsapp_business_management` permissions.
4. In ERPNext, open **Techy Ops Settings → WhatsApp (Customer App)** and fill in:
   - **Phone Number ID**: shown in the app's *WhatsApp → API Setup*. It is the ID, not the phone number.
   - **Access Token**: the permanent token from step 3.
   - **App Secret**: the app's *Settings → Basic*.
   - **Update Template** and **Invitation Template**: the template names, if you did not use `plant_update` and `plant_invite`.
   - **Template Language**: the code of the language the templates were approved in, for example `en` or `en_US`. It must match exactly.
   - **Default Country Code**: `254` turns 0712 345 678 into +254 712 345 678.
5. Set up the **webhook**, so delivery statuses and STOP replies come back. In the app's *WhatsApp → Configuration*:
   - **Callback URL**: `https://<your site>/api/method/projectit.whatsapp.webhook`
   - **Verify token**: the **Webhook Verify Token** shown in Techy Ops Settings.
   - Subscribe to the **messages** field.
6. Tick **Send WhatsApp Messages** and save.
7. Check it works. In Techy Ops, open **Customer plants → Accounts → Send a test message**, enter your own number, and look for the message on your phone and in **Techy WhatsApp Message**.

## The two templates

Submit these exactly. The numbers in `{{ }}` are filled in by the app. Meta asks for a sample value for each.

**`plant_update`** (Utility)

> Hello {{1}}, here is an update about your water plant: {{2}}
>
> Open the plant app for details. Reply STOP to stop these messages.

Samples: `{{1}}` = `Amina`; `{{2}}` = `Tina, our technician, is on the way to RO System 1000 LPH. They should arrive in about 30 minutes.`

**`plant_invite`** (Utility)

> Hello {{1}}, {{2}} has given you access to the plant app for {{3}}: log your plant readings, follow how it is running and ask us for service.
>
> Set your password and sign in here: {{4}}
>
> The link works once. Reply STOP if you do not want messages from us.

Samples: `{{1}}` = `Amina`; `{{2}}` = your company name; `{{3}}` = `Bahari Clinic`; `{{4}}` = `https://your-site/update-password?key=abc123`

If Meta rejects the invitation template because of the link in the text, tell us. It can be changed to send the link as a button instead.

## Costs

Meta charges per conversation. Template messages like these are *utility* conversations, priced per country. Kenya's rates are on Meta's pricing page. Replies from the customer within 24 hours are part of the same conversation.

## When something fails

**Techy WhatsApp Message** shows the reason Meta gave. The usual ones:

| Meta's reason | What to do |
| --- | --- |
| *Template name does not exist in the translation* | The template name or language in settings does not match the approved template. |
| *Recipient phone number not in allowed list* | You are still using Meta's test number. Add your business number. |
| *Authentication error* | The token expired or was not a permanent system-user token. |
| *Re-engagement message* | Normal for free-form messages. This app only sends templates, so it should not happen. |
