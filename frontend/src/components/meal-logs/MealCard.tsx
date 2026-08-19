import { AuthedImage } from "@/components/authed-image";
import { formatMealTime } from "@/components/meal-logs/groupByDay";
import { MEAL_SLOT_LABELS, type MealLogOut } from "@/lib/api/mealLogs";

const REACTION_EMOJI: Record<"happy" | "neutral" | "sad", string> = {
  happy: "😊", neutral: "😐", sad: "😞",
};

export function MealCard({
  meal, photoUrl, children, showReaction = false,
}: {
  meal: MealLogOut;
  photoUrl: string;
  children?: React.ReactNode; // HC view slots its reaction-picker in here; client view passes nothing
  // PHASE-03 final review Finding I4: defaults to false — nothing in the product spec
  // (D-26) or this plan's Design Decisions authorized showing the HC's reaction to the
  // client, and an unexplained sad-face reaction with no context could read as
  // confusing or hurtful. The HC-side view opts in explicitly.
  showReaction?: boolean;
}) {
  return (
    <div className="w-56 flex-shrink-0 space-y-2 rounded-md border border-border p-3">
      <AuthedImage url={photoUrl} alt={meal.photo_original_filename} className="h-32 w-full rounded object-cover" />
      <p className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
        {MEAL_SLOT_LABELS[meal.meal_slot]}
      </p>
      {meal.description && <p className="font-sans text-sm text-foreground">{meal.description}</p>}
      <p className="font-sans text-xs text-muted-foreground">
        {meal.captured_at ? formatMealTime(meal.captured_at) : "Time not available"}
      </p>
      {showReaction && meal.hc_reaction && <p className="text-lg">{REACTION_EMOJI[meal.hc_reaction]}</p>}
      {children}
    </div>
  );
}
