/** The Android app's build numbers (components/appupdate.tsx). */

/** The installed build, from the app's user agent ("PashupatastraApp/0.1.<build>"); null in a browser. */
export function installedBuild(userAgent: string): number | null {
  const match = userAgent.match(/PashupatastraApp\/\d+\.\d+\.(\d+)/);
  return match ? Number(match[1]) : null;
}

/** The latest build, from the `android` release's title ("Android app (test build <n>)"). */
export function releasedBuild(title: string): number | null {
  const match = title.match(/build (\d+)/);
  return match ? Number(match[1]) : null;
}
