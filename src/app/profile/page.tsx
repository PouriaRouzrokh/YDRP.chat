"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDate } from "@/lib/utils";
import { profileService } from "@/services/profile";
import { User } from "@/types";

export default function ProfilePage() {
  const [loading, setLoading] = useState(true);
  const [profileData, setProfileData] = useState<{
    user: User | null;
    totalConversations: number;
    lastConversationDate: Date | null;
  }>({
    user: null,
    totalConversations: 0,
    lastConversationDate: null,
  });
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadProfileData() {
      try {
        setLoading(true);
        const data = await profileService.getUserProfile();
        setProfileData(data);
        setError(null);
      } catch (err) {
        setError("Failed to load profile data. Please try again later.");
        console.error(err);
      } finally {
        setLoading(false);
      }
    }

    loadProfileData();
  }, []);

  return (
    <div className="max-w-4xl mx-auto py-8 px-4">
      <h1 className="text-2xl font-bold mb-6">Profile</h1>

      {loading ? (
        <div className="flex justify-center py-8">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent"></div>
        </div>
      ) : error ? (
        <div className="p-4 bg-destructive/10 text-destructive rounded">
          {error}
        </div>
      ) : (
        <div className="grid gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Account Information</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <h3 className="text-sm font-medium text-muted-foreground">
                    Full Name
                  </h3>
                  <p className="text-lg">
                    {profileData.user?.full_name || "Not available"}
                  </p>
                </div>
                <div>
                  <h3 className="text-sm font-medium text-muted-foreground">
                    Email
                  </h3>
                  <p className="text-lg">
                    {profileData.user?.email || "Not available"}
                  </p>
                </div>
                <div>
                  <h3 className="text-sm font-medium text-muted-foreground">
                    Password
                  </h3>
                  <p className="text-lg text-muted-foreground">••••••••••</p>
                </div>
                <div>
                  <h3 className="text-sm font-medium text-muted-foreground">
                    Account Type
                  </h3>
                  <p className="text-lg">
                    {profileData.user?.is_admin
                      ? "Administrator"
                      : "Standard User"}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Conversation Statistics</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <h3 className="text-sm font-medium text-muted-foreground">
                    Total Conversations
                  </h3>
                  <p className="text-2xl font-bold">
                    {profileData.totalConversations}
                  </p>
                </div>
                <div>
                  <h3 className="text-sm font-medium text-muted-foreground">
                    Last Conversation
                  </h3>
                  <p className="text-lg">
                    {profileData.lastConversationDate
                      ? formatDate(profileData.lastConversationDate)
                      : "No conversations yet"}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
