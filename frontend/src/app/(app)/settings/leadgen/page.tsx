"use client";

import { useEffect, useState } from "react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { getLeadgenConfig, initLeadgenConfig, type LeadgenConfigStatus } from "@/lib/api/leadgen";
import { SetupTab } from "./SetupTab";
import { IntakeFormTab } from "./IntakeFormTab";
import { TestPanelTab } from "./TestPanelTab";

export default function LeadgenSettingsPage() {
  const [config, setConfig] = useState<LeadgenConfigStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [initError, setInitError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("setup");

  useEffect(() => {
    getLeadgenConfig().then(setConfig).finally(() => setLoading(false));
  }, []);

  async function handleInit() {
    setInitError(null);
    try {
      const result = await initLeadgenConfig();
      setConfig(result);
    } catch (err) {
      setInitError(err instanceof Error ? err.message : "Setup failed");
    }
  }

  if (loading) return <div className="p-6">Loading...</div>;

  if (!config?.configured) {
    return (
      <div className="p-6 max-w-lg">
        <h1 className="text-xl font-semibold mb-2">Set up lead generation</h1>
        <p className="text-sm text-muted-foreground mb-4">
          This creates your shareable intake link. Your name and business details come from your{" "}
          <a href="/settings/profile" className="underline">profile settings</a> — make sure that&apos;s filled in first.
        </p>
        {initError && (
          <p className="text-sm text-destructive mb-4">
            {initError}{" "}
            <a href="/settings/profile" className="underline">Go to profile settings</a>
          </p>
        )}
        <button
          onClick={handleInit}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
        >
          Set up my intake link
        </button>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="mb-4">
        <p className="text-sm text-muted-foreground">Your intake link</p>
        <code className="text-sm">tapas.app/intake/{config.hc_slug}</code>
      </div>
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <div className="overflow-x-auto">
          <TabsList variant="line">
            <TabsTrigger value="setup">Setup</TabsTrigger>
            <TabsTrigger value="intake-form">Intake Form</TabsTrigger>
            <TabsTrigger value="test-panel">Test Panel</TabsTrigger>
          </TabsList>
        </div>
        <div className="mt-6">
          <TabsContent value="setup">
            <SetupTab config={config} onUpdate={setConfig} />
          </TabsContent>
          <TabsContent value="intake-form">
            <IntakeFormTab config={config} onUpdate={setConfig} />
          </TabsContent>
          <TabsContent value="test-panel">
            <TestPanelTab config={config} onUpdate={setConfig} />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}
