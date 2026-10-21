# The plant app (for customers)

The plant app is for the people who run a water-treatment plant we installed. Its address is `/techy-app/plant`, and it can be installed on a phone like any app. Each day, an operator logs the readings from the plant's gauges. We and the customer use those logs to follow how the plant is running and when it needs service.

## Who uses it

| Account | Can do |
| --- | --- |
| **Customer admin** | See every machine of their company. Log readings. Invite their own operators, choose which machines each operator looks after, switch operators off and send them a new sign-in link. |
| **Operator** | See and log only the machines given to them. |

We create the first account (normally the customer admin) when the plant is registered. The person gets an email with a link to choose their password. The link works once. If it has expired, ask us, or your admin, for a new one.

A customer account can only ever see its own company's machines. It cannot open the staff apps, ERPNext, prices or anything internal.

## Home: your plant at a glance

- **Status** in plain words: *Running well*, *Needs attention* or *Action needed*, with the reasons. Examples: the membranes need cleaning, the machine is reported as not working, or no log for a while.
- **Key numbers**: water produced, water quality (TDS of the clean water), recovery (the share of feed water that becomes clean water) and running hours. Each shows how it changed since last week.
- **Trends** over 30 or 90 days. **Membrane condition** compares water output and salt let through with the last time the membranes were clean, corrected for water temperature and pressure. The red line is where they need cleaning. Every chart has a **Table** view.
- **What's next**: the next planned visit, when service is due by running hours (an estimate), and when the warranty and service contract end.
- **Your logs**: how many of the last 30 days were logged.

## Logging readings

Open **Log**, read the gauges, and type each number in. The form lists the machine's readings in the order you walk the plant: feed and concentrate pressure, then water quality (TDS), flows and temperature. Readings marked *(optional)* can be left empty. The last value of each reading is shown beside it as a guide.

- **Unusual numbers.** If a number is far from the usual for that gauge (often a typo, such as an extra zero), the app asks you to check it. Correct it, or save it as it is if the gauge really reads that.
- **Counters only go up.** Running hours cannot be lower than last time. If a meter was replaced, tell us.
- **Note and photo.** Add a note about anything unusual (a leak, a noise, an alarm, filters changed) and, if you like, a photo of the gauges.
- **No signal?** Save the log anyway. It waits on the phone ("1 log waiting to send") and sends by itself when the phone is back online, with the time it was taken.
- **Out of range.** If a reading is above or below its limit, the app says what to check first and when to call us, with an **Ask for service** button that fills in the reading. Home shows the same advice while the latest reading is out of range.
- **Typos afterwards.** Under **Recent logs**, **Correct a typo** fixes your own log for a day after saving it. We can see that it was corrected.

The top of the Log page shows whether today's log is done. Each machine is logged once a day unless we agreed otherwise (twice a day, once a week, or not at all).

## Filters and chemicals

Under the log, **Filters and chemicals** lists what the machine uses, when each is next due and how much is on site.
- **Changed** (filters) records a change: it uses the usual amount and starts the countdown again. **Topped up** (chemicals) asks how much was used.
- **Due now**, **Due in 2 days** and **Running low** also show on Home and in the plant's status.
- **Order more** asks us for more. We send a quotation. The supply shows *Ordered* until the delivery arrives.
- **⋯ → A delivery arrived** adds stock. **⋯ → Correct what is on site** fixes the count.

## Service

- **Ask for service**: say what is wrong, add details and a photo, and tick **Urgent** if the plant has stopped or the water is not safe. The request goes straight to our team.
- **Your requests** shows each request your company raised for the machine. It shows as *Received*, then *Accepted* (we will schedule a visit), *Scheduled* with the date, *In progress* and *Done*. If we can't help with a request, it shows *Closed* with our reply.
- **Past visits** lists what was done and by whom. **Service report** opens the visit's report as a PDF. It has no prices; the invoice has those.
- **Rate this visit** (1 to 5 stars and an optional comment) for 30 days after a visit.
- **Monthly reports** (customer admins): a PDF for each month with every machine's water produced, hours run, days logged, water quality, membrane condition, visits, requests, filters and chemicals, and what we recommend. Admins also get last month's report by email on the 1st; switch it off in Account.
- **Warranty and service contract** shows the warranty end date and, if you have a contract, what it covers: service visits (and how many are done), labour, call-outs, response and fix times, and parts.

## Notifications

Turn on **Notifications → On this phone** in **Account** to get alerts even when the app is closed. On an iPhone, first add the app to the home screen (Share, then Add to Home Screen; iOS 16.4 or later).

- **Visits and reports:** a visit is planned or moved, our technician is on the way (with when they expect to arrive) or has started work, the visit is done and its report is ready, or the membranes need cleaning and we are planning it.
- **Log reminders:** once a day, after 10:00, while a machine's log is due. Someone with several machines gets one reminder listing them. Reminders go to the machine's operators, or to the admin when it has none.
- **Replies to your requests** always arrive.

Each person can switch *Visits and reports* and *Log reminders* off. Tapping a notification opens the right page in the plant app.

## Account

**Account** shows your machines, light or dark appearance, and how to reach us. A customer admin also sees **People**, where they invite and manage operators.
