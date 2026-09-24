import React from 'react';
import { ProtectedStorageGuide } from '@/src/components/ProtectedStorageGuide';

export default function Junk() {
  return (
    <ProtectedStorageGuide
      title="App Storage"
      icon="trash-outline"
      description="Manage app storage safely"
      guidance="Android decides which app caches can be cleared. DevicePulse can clear its own temporary cache from Smart Scan; use Android Storage to review other apps."
    />
  );
}
