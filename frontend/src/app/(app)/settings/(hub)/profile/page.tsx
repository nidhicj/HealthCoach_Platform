"use client";

import { useEffect, useState } from "react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { getProfile, updateProfile, type SettingsProfile } from "@/lib/api/settings";

export default function SettingsProfilePage() {
  const [profile, setProfile] = useState<SettingsProfile | null>(null);
  const [businessName, setBusinessName] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [loadError, setLoadError] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    getProfile()
      .then((p) => {
        setProfile(p);
        setBusinessName(p.business_name ?? "");
        setFirstName(p.first_name ?? "");
        setLastName(p.last_name ?? "");
      })
      .catch(() => setLoadError(true));
  }, []);

  const trimmedFirstName = firstName.trim();
  const trimmedLastName = lastName.trim();
  const requiredFieldsMissing = trimmedFirstName === "" || trimmedLastName === "";

  async function handleSave() {
    if (requiredFieldsMissing) {
      setSaveError(true);
      setSaved(false);
      return;
    }
    setSaving(true);
    setSaveError(false);
    setSaved(false);
    try {
      const updated = await updateProfile(
        businessName.trim() === "" ? null : businessName,
        trimmedFirstName,
        trimmedLastName,
      );
      setProfile(updated);
      setBusinessName(updated.business_name ?? "");
      setFirstName(updated.first_name ?? "");
      setLastName(updated.last_name ?? "");
      setSaved(true);
    } catch {
      setSaveError(true);
    } finally {
      setSaving(false);
    }
  }

  const loading = profile === null && !loadError;

  return (
    <div className="max-w-2xl space-y-8">
      {/* Page header */}
      <div>
        <p className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
          Account
        </p>
        <h1 className="mt-1 font-heading text-4xl font-black text-foreground">
          Profile
        </h1>
      </div>

      {loading ? (
        <div className="space-y-3">
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
        </div>
      ) : loadError ? (
        <p className="font-sans text-sm text-destructive">Could not load profile.</p>
      ) : (
        <>
          {/* Editable name + business name */}
          <div className="space-y-4">
            <div className="space-y-2">
              <label
                htmlFor="first-name"
                className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground"
              >
                First name
                <span className="text-destructive"> *</span>
              </label>
              <Input
                id="first-name"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                placeholder="First name"
                required
              />
            </div>

            <div className="space-y-2">
              <label
                htmlFor="last-name"
                className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground"
              >
                Last name
                <span className="text-destructive"> *</span>
              </label>
              <Input
                id="last-name"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                placeholder="Last name"
                required
              />
            </div>

            <div className="space-y-2">
              <label
                htmlFor="business-name"
                className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground"
              >
                Business name
              </label>
              <Input
                id="business-name"
                value={businessName}
                onChange={(e) => setBusinessName(e.target.value)}
                placeholder="Your practice name"
              />
            </div>

            <Button onClick={handleSave} disabled={saving || requiredFieldsMissing}>
              {saving ? "Saving…" : "Save"}
            </Button>
            {saveError && requiredFieldsMissing && (
              <p className="font-sans text-xs text-destructive">
                First name and last name are required.
              </p>
            )}
            {saveError && !requiredFieldsMissing && (
              <p className="font-sans text-xs text-destructive">Could not save. Try again.</p>
            )}
            {saved && !saveError && (
              <p className="font-sans text-xs text-muted-foreground">Saved</p>
            )}
          </div>

          <Separator />

          {/* Read-only Google identity block */}
          <div className="space-y-3">
            <p className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
              Signed in as
            </p>
            <div className="flex items-center gap-3">
              <Avatar size="lg">
                <AvatarImage src={profile!.photo_url ?? undefined} alt="" />
                <AvatarFallback>
                  {(profile!.display_name ?? profile!.email).charAt(0).toUpperCase()}
                </AvatarFallback>
              </Avatar>
              <div className="min-w-0 space-y-0.5">
                <p className="font-sans text-sm font-bold text-foreground truncate">
                  {profile!.display_name ?? "—"}
                </p>
                <p className="font-sans text-xs text-muted-foreground truncate">
                  {profile!.email} · via Google
                </p>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
