import { AuthedImage } from "@/components/authed-image";
import { MEAL_SLOT_LABELS, type MealLogOut } from "@/lib/api/mealLogs";

const REACTION_EMOJI: Record<"happy" | "neutral" | "sad", string> = {
  happy: "😊", neutral: "😐", sad: "😞",
};

export function MealCard({
  meal, photoUrl, children,
}: {
  meal: MealLogOut;
  photoUrl: string;
  children?: React.ReactNode; // HC view slots its reaction-picker in here; client view passes nothing
}) {
  return (
    <div className="w-56 flex-shrink-0 space-y-2 rounded-md border border-border p-3">
      <AuthedImage url={photoUrl} alt={meal.photo_original_filename} className="h-32 w-full rounded object-cover" />
      <p className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
        {MEAL_SLOT_LABELS[meal.meal_slot]}
      </p>
      {meal.description && <p className="font-sans text-sm text-foreground">{meal.description}</p>}
      <p className="font-sans text-xs text-muted-foreground">
        {meal.captured_at
          ? new Date(meal.captured_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
          : "Time not available"}
      </p>
      {meal.hc_reaction && <p className="text-lg">{REACTION_EMOJI[meal.hc_reaction]}</p>}
      {children}
    </div>
  );
}
