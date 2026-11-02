import type { Metadata } from "next";
import Link from "next/link";

import { Page, Panel } from "@/components/ui";

export const metadata: Metadata = {
  title: "Privacy",
  description:
    "What the Pashupatastra site and Android app collect, where it is kept, and what never leaves your phone.",
};

/**
 * The privacy policy, for the site and the Android app (RP-85: Google Play needs a
 * public one). Every statement is checked against the code it describes, named in
 * the comments, so a change to what is collected has a place here to land:
 *
 * - page counts: `middleware.ts` → `/impact/view` (`routes.record_view`): route and day only.
 * - questions: `routes._asked`, kept in the append-only audit trail, shown on /audit.
 * - on the device: theme and training progress (localStorage); the app's prefs
 *   (`IncidentWatch`, `IncidentsWidget`): seen incident ids and the widget's counts.
 *
 * - accounts (since 1 Nov 2026): `services/api/app/accounts.py`: an id and a name; an email and a
 *   scrypt hash for email accounts; Google's subject id and verified email for Google accounts; nothing
 *   for guests. Training results and company memberships. `DELETE /me` erases all of it.
 *
 * Plain sentences, no legal boilerplate standing in for facts.
 */
const UPDATED = "1 November 2026";

export default function PrivacyPage() {
  return (
    <Page title="Privacy" description={`What is collected, where it is kept, and what is not. Updated ${UPDATED}.`}>
      <div className="max-w-3xl space-y-4 text-sm leading-relaxed">
        <Panel title="In short">
          <p>
            Accounts are optional: everything public works without one. There is no advertising and no tracking
            across other sites or apps. Nothing is sold or shared for marketing. The app asks for no location,
            contacts, photos, camera or microphone.
          </p>
        </Panel>

        <Panel title="What is collected">
          <ul className="list-disc space-y-2 pl-5">
            <li>
              <strong>Page counts.</strong> Each page view adds one to a daily count for that page's path, such
              as <code>/incidents</code>. No identifier, address or device detail is stored with it. The totals
              are public on <Link href="/impact" className="underline">Impact</Link>.
            </li>
            <li>
              <strong>Questions to Sati AI.</strong> Sati, the investigation agent, keeps each question (up to 240
              characters) with its answer's model and cost in an append-only audit trail, so any answer can be
              explained later. The trail is public on <Link href="/audit" className="underline">Audit</Link>{" "}
              and nothing identifies who asked. Because it is public and permanent, do not type personal or
              confidential details into a question.
            </li>
          </ul>
        </Panel>

        <Panel title="If you create an account">
          <ul className="list-disc space-y-2 pl-5">
            <li>
              <strong>What is kept.</strong> Your name as you typed it. For an email account, the address and a
              one-way scrypt hash of your password (never the password itself), and whether you have confirmed
              the address from the link we email (only a hash of that link is kept, for a day). For Google sign-in, Google's
              account id and your verified address, which Google shares when you choose to continue. A guest
              account keeps nothing but a random id.
            </li>
            <li>
              <strong>Your training record.</strong> Each module's best and last score, attempts and whether you
              passed. Scores are marked in your browser, so a company reads them as your own record, not as a
              supervised exam.
            </li>
            <li>
              <strong>Companies.</strong> If you join a company with its invite code, that company's owner and
              admins can see your name, email, training record and when you were last active. Nobody else can.
            </li>
            <li>
              <strong>A company&apos;s own alerts.</strong> If a company connects its systems, the alerts they send
              (a title, severity, source, the account or host involved, and details) are kept with that company and
              shown only to its members. The company decides what its systems send; nothing in them reaches the
              public audit trail, which records only that an intake key was made or revoked.
            </li>
            <li>
              <strong>Never public.</strong> The audit trail records that an account or company was created, never
              whose. No IP address or device detail is kept with an account.
            </li>
            <li>
              <strong>Deleting it.</strong> <Link href="/account" className="underline">Account</Link> → Delete
              account erases the account, its sign-in, its memberships and its training record at once.
            </li>
          </ul>
        </Panel>

        <Panel title="What stays on your device">
          <ul className="list-disc space-y-2 pl-5">
            <li>
              Your theme choice and your training progress, in the browser's or app's own storage, and your
              sign-in token if you have an account. Signing out removes the token.
            </li>
            <li>
              In the Android app: whether alerts are on, which incidents you have already been alerted about,
              and the home-screen widget's last counts. Removing the app removes them.
            </li>
          </ul>
        </Panel>

        <Panel title="Alerts in the Android app">
          <p>
            With alerts on, the app checks the public incident list about every 15 minutes and shows a
            notification when an incident newly awaits approval or a critical one opens. The phone only asks;
            it sends nothing about you. Android asks for your permission first, and the switch under More turns
            alerts off.
          </p>
        </Panel>

        <Panel title="Who handles the traffic">
          <p>
            The site is hosted on Vercel and the API runs on Amazon Web Services. Like any web host, they
            process your IP address to deliver the pages and may keep it briefly in their own operational logs
            under their own privacy policies. This project keeps no IP addresses. Links to outside sources,
            such as a feed's own record, open in your browser and are governed by that site.
          </p>
        </Panel>

        <Panel title="Children">
          <p>The product is for security professionals and learners. It is not directed at children under 13.</p>
        </Panel>

        <Panel title="Changes and contact">
          <p>
            If what is collected changes, this page changes first, with a new date. Questions or requests:{" "}
            <a href="https://github.com/preetraval45/PASHUPATASTRA/issues" className="underline">
              open an issue on the project's repository
            </a>
            .
          </p>
        </Panel>
      </div>
    </Page>
  );
}
