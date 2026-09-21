import { useState } from 'react';
import { useTranslation } from 'react-i18next';

export function Profile({ avatar, logo }: { avatar: string; logo: string }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  return (
    <main>
      <h1>Profile</h1>
      <img src={avatar} />
      <img src={logo} alt="" />
      <input type="search" placeholder="Search" />
      <label htmlFor="bio">{t('profile.bio')}</label>
      <textarea id="bio" />
      <p>{t('profile.welcome')}</p>
      <button type="button" onClick={() => setOpen(true)}>Edit</button>
      {open && (
        <div role="dialog">
          <p>Update your details</p>
          <button type="button" onClick={() => setOpen(false)}>Close</button>
        </div>
      )}
    </main>
  );
}
