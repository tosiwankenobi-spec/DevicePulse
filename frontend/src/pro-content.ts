export const PRO_TOOLS = [
  { id: 'coach', title: 'Personal AI Coach', detail: 'Storage, battery habits and safe cleanup questions, with saved conversations.', icon: 'chatbubbles-outline', route: '/(tabs)/coach' },
  { id: 'history', title: 'Cleanup journal', detail: 'Your recorded cleanups, dates and measured space changes.', icon: 'time-outline', route: '/history' },
  { id: 'report', title: 'Shareable progress report', detail: 'Create a report from your actual readings and cleanup history.', icon: 'share-social-outline', route: '/cleanup-report' },
  { id: 'family', title: 'Family dashboard', detail: 'Invite Pro members to share their latest readings voluntarily. No remote deletion.', icon: 'people-outline', route: '/family' },
] as const;
export const PRO_ROUTINES = [
  { id: 'storage', title: 'Weekly storage reset', detail: 'Keep only what you need, without blind deletion.', steps: [
    { id: 'measure', title: 'Measure first', body: 'Run a Smart Storage Check. Note available space and DevicePulse cache.', route: '/smart-scan' },
    { id: 'review', title: 'Review downloads', body: 'Open Files by Google or Android Files. Review old installers and downloads individually. Keep anything you cannot identify.' },
    { id: 'cache', title: 'Clear only disposable cache', body: 'Use DevicePulse’s confirmed cache cleanup. Android Settings → Apps → Storage → Clear cache can help for other apps; avoid Clear storage.', route: '/smart-scan' },
  ] },
  { id: 'battery', title: 'Battery habits review', detail: 'Improve everyday habits—not invented battery health.', steps: [
    { id: 'usage', title: 'Check real battery usage', body: 'In Android Settings → Battery → Battery usage, review the apps you recognize. High use can be normal for apps you use often.', route: '/(tabs)/insights' },
    { id: 'background', title: 'Review background activity', body: 'Restrict only apps you do not need running. Keep messaging, alarms, accessibility and health apps working. Android menus vary by phone.' },
    { id: 'recheck', title: 'Compare after normal use', body: 'Use the phone normally for a day, then review Battery usage again. Do not expect an instant battery-capacity increase.', route: '/(tabs)/insights' },
  ] },
  { id: 'privacy', title: 'Monthly privacy tune-up', detail: 'A personal review, not a security scan.', steps: [
    { id: 'permissions', title: 'Review permissions', body: 'Android Settings → Privacy → Permission manager: check camera, microphone and location access. Remove permissions only when you understand the effect.' },
    { id: 'updates', title: 'Check system and app updates', body: 'Check Android’s Software update screen and Google Play’s app updates. DevicePulse cannot measure your security patch level.' },
    { id: 'sessions', title: 'Review DevicePulse sessions', body: 'Review your active sign-ins and revoke ones you no longer recognize.', route: '/sessions' },
  ] },
] as const;
