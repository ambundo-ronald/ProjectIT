# Techy App attendance

Techy App records work punches. HRMS decides attendance using the employee's shift rules; checkout is not an automatic declaration of Present.

## Administrator setup

1. Link the user's account to exactly one active Employee using User ID, enable the stored `WorkIT` mobile module (shown as Techy Work), and allocate the employee to a project.
2. Grant the necessary scoped permissions: Project read; Timesheet create/read/write/submit; Employee Checkin create; and File create with access to the attached Timesheet. Existing employee restrictions should remain in place. The custom punch APIs also enforce ownership and project allocation on the server.
3. Configure Work Time Settings with start/end times and regular/overtime activity types. These settings split project time only; HRMS attendance thresholds come from Shift Type.
4. Assign a Shift Type through an active Shift Assignment or the Employee's default shift. Enable Auto Attendance and set Process Attendance After appropriately.
5. Choose **Strictly based on Log Type in Employee Checkin**. Choose the working-hours rule to match policy: every valid IN/OUT pair excludes gaps between project sessions; first IN/last OUT includes them. Set Half Day/Absent thresholds, holidays, and late/early rules according to company policy.
6. Configure the allowed pre-shift and post-shift punch windows. Punches outside those windows may remain off-shift and require HR review.
7. Configure Last Sync of Checkin. When Techy App is the sole live punch source, enable **Automatically update Last Sync of Checkin**. If other devices upload delayed logs, keep the watermark under the synchronization process's control until those logs have arrived.
8. Ensure the HRMS scheduler/workers run. HRMS attempts processing after the last-sync watermark passes the shift's actual end, including its checkout buffer. HR can also use **Mark Auto Attendance** on Shift Type.

References: [HRMS Shift Type](https://docs.frappe.io/hr/shift-type), [HRMS Auto Attendance](https://docs.frappe.io/hr/auto-attendance).

## Employee experience

- Capture a photo and allow location access to check in or out.
- The server supplies the timestamp and employee identity. Timesheet, private photo, and punch are written in the same request transaction. A validation/permission failure is returned to the phone; Frappe rolls back database writes for that failed POST.
- Open sessions survive page reloads and midnight. Retrying an existing check-in returns that session; retrying completed checkout does not create another OUT log.
- My attendance shows the processing state and the latest 14 non-cancelled attendance records. Drafts are explicitly labeled. Use Refresh after HRMS processes the shift.
- Missing/disabled shifts, off-shift punches, skipped logs, and incomplete processing settings prompt HR review. The app never advances the global last-sync watermark just because one employee checked out.

## Updating an existing site

Build this app, run the site's migration and clear its cache, then restart the deployment services so the removed Timesheet attendance hook is no longer cached:

```sh
bench build --app projectit
bench --site your-site migrate
bench --site your-site clear-cache
```

The previous hook may have created draft Attendance records. HR must review those before processing affected dates because existing drafts can block HRMS auto-attendance. This update does not delete, submit, or overwrite historical attendance. Review old draft timesheets without a linked IN log as well; the app cannot infer a missing punch accurately. Timesheet cancellation does not undo an already processed HRMS Attendance record; attendance corrections remain an HR operation.

## Validation

Local regression tests:

```sh
python -m unittest discover -s tests -v
yarn build
```

Endpoint tests use mocked Frappe services. They check ownership, retries, error propagation, final OUT timestamps, setup messages, and time splitting; they do not prove database rollback or HRMS processing against a live site.

Required v16 staging checks:

- Login as an Employee with the scoped permissions above. Check in, reload, and check out; confirm exactly one IN and OUT with photos attached privately and the timesheet submitted.
- Try another employee's timesheet, an unallocated project, missing GPS, and invalid photos. Confirm no unauthorized write. Force an OUT insert or photo failure and verify the entire POST's database writes rolled back.
- Repeat each POST after a simulated lost response and send concurrent requests from two devices; confirm one session/punch pair.
- Test regular hours, overtime boundaries, midnight/overnight shifts, and multiple project sessions on one day.
- Process shifts with hours above/below the configured Present/Half Day/Absent thresholds. Confirm HRMS links logs to the expected submitted Attendance record, including holidays/approved leave and existing draft/submitted attendance.
- Verify that off-shift/skipped logs are reported for review and that pending attendance changes after HRMS processing and Refresh.
