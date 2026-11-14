import React from 'react';
import { ProtectedStorageGuide } from '@/src/components/ProtectedStorageGuide';

export default function Forecast() {
  return (
    <ProtectedStorageGuide
      title="Storage Planning"
      icon="trending-up-outline"
      description="Review current storage, not invented forecasts"
      guidance="DevicePulse measures present free space accurately. Android Storage provides the protected file details needed to decide what to keep or remove."
    />
  );
}
