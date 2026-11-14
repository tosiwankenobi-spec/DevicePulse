import React from 'react';
import { ProtectedStorageGuide } from '@/src/components/ProtectedStorageGuide';

export default function AutoClean() {
  return (
    <ProtectedStorageGuide
      title="Protected Cleanup"
      icon="shield-checkmark-outline"
      description="Android requires cleanup approval"
      guidance="DevicePulse does not schedule silent deletion of photos, downloads, duplicates or other apps' data. Use Android Storage whenever you want to review files safely."
    />
  );
}
