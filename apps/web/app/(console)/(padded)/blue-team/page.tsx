import { redirect } from "next/navigation";

/** The drill list is the Training page now; the drills keep their URLs. */
export default function BlueTeamPage() {
  redirect("/training");
}
