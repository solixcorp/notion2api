/**
 * Notion account info extraction script (legacy manual fallback flow)
 *
 * Recommended: run `python login.py` first. That login script automatically opens a temporary
 * Chrome/Edge debug window and extracts token_v2 and account/workspace fields from the local
 * browser session.
 *
 * If the automatic login flow is unavailable, use this manual script:
 * 1. Log in to https://www.notion.so/ai in your browser
 * 2. Make sure the top-left account switcher is set to the account you want to extract
 * 3. F12 → Application → Cookies → copy the value of token_v2
 * 4. F12 → Console → paste this script → press Enter
 * 5. If you have multiple accounts/workspaces, follow the prompts to choose
 * 6. Paste the output JSON into accounts.json, replacing YOUR_TOKEN_V2
 */
(async () => {
  try {
    // ─── Step 1: Get all accessible users and spaces ───
    // getSpaces returns all users visible to the current token (including multi-account)
    let allUsers = {};  // user_id → {name, email}
    let allSpaces = {}; // space_id → {name, plan, members}
    let spaceViewMap = {}; // space_id → space_view_id

    // Try getSpaces (returns more complete multi-account data)
    try {
      const r1 = await fetch('/api/v3/getSpaces', {
        method: 'POST', headers: { 'content-type': 'application/json' },
        body: '{}', credentials: 'include'
      });
      const d1 = await r1.json();
      // getSpaces returns { "user_id_1": { space: {...}, ... }, "user_id_2": {...} }
      if (d1 && typeof d1 === 'object' && !d1.recordMap) {
        for (const [userId, userData] of Object.entries(d1)) {
          if (!userData || typeof userData !== 'object') continue;
          // Extract user info
          const nu = userData.notion_user;
          if (nu) {
            for (const [nuid, nuData] of Object.entries(nu)) {
              const v = nuData?.value?.value || nuData?.value || nuData || {};
              allUsers[nuid] = {
                name: v.given_name || v.name || v.family_name || '',
                email: v.email || ''
              };
            }
          }
          // Extract space info
          const sp = userData.space;
          if (sp) {
            for (const [sid, sData] of Object.entries(sp)) {
              const v = sData?.value?.value || sData?.value || sData || {};
              if (!allSpaces[sid]) {
                allSpaces[sid] = {
                  name: v.name || '',
                  plan: v.plan_type || v.subscription_tier || ''
                };
              }
            }
          }
          // Extract space_view
          const sv = userData.space_view;
          if (sv) {
            for (const [svid, svData] of Object.entries(sv)) {
              const v = svData?.value?.value || svData?.value || svData || {};
              if (v.space_id) spaceViewMap[v.space_id] = svid;
            }
          }
        }
      }
    } catch (e) { /* getSpaces failed, fall back to loadUserContent */ }

    // Fallback: loadUserContent
    const r2 = await fetch('/api/v3/loadUserContent', {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: '{}', credentials: 'include'
    });
    const d2 = (await r2.json()).recordMap || {};

    // Merge users
    for (const [nuid, nuData] of Object.entries(d2.notion_user || {})) {
      if (allUsers[nuid]) continue;
      const v = nuData?.value?.value || nuData?.value || nuData || {};
      allUsers[nuid] = {
        name: v.given_name || v.name || v.family_name || '',
        email: v.email || ''
      };
    }
    // Merge spaces
    for (const [sid, sData] of Object.entries(d2.space || {})) {
      if (allSpaces[sid]) continue;
      const v = sData?.value?.value || sData?.value || sData || {};
      allSpaces[sid] = {
        name: v.name || '',
        plan: v.plan_type || v.subscription_tier || ''
      };
    }
    // Merge space_view
    for (const [svid, svData] of Object.entries(d2.space_view || {})) {
      const v = svData?.value?.value || svData?.value || svData || {};
      if (v.space_id && !spaceViewMap[v.space_id]) spaceViewMap[v.space_id] = svid;
    }

    // Read notion_user_id from cookie (the currently active account in the UI)
    const cookieUserId = document.cookie.split(';')
      .map(c => c.trim())
      .find(c => c.startsWith('notion_user_id='))
      ?.split('=')[1] || '';

    const userList = Object.entries(allUsers);
    const spaceList = Object.entries(allSpaces).map(([id, s]) => ({
      space_id: id, name: s.name, plan: s.plan, space_view_id: spaceViewMap[id] || ''
    }));

    if (userList.length === 0) {
      console.error('❌ No user info found. Please confirm you are logged in to Notion.');
      return;
    }

    // ─── Display & select user ───
    console.log('\n');
    console.log('%c═══════════════════════════════════════════════', 'color:#00a699');
    console.log('%c  Notion Account Info Extraction Tool', 'font-size:15px;font-weight:bold;color:#00a699');
    console.log('%c═══════════════════════════════════════════════', 'color:#00a699');
    console.log('');

    let chosenUserId, chosenUserName, chosenUserEmail;

    if (userList.length === 1) {
      chosenUserId = userList[0][0];
      chosenUserName = userList[0][1].name;
      chosenUserEmail = userList[0][1].email;
      console.log(`%c👤 User: ${chosenUserName || '(unknown)'} ${chosenUserEmail ? '(' + chosenUserEmail + ')' : ''}`, 'font-size:13px');
    } else {
      console.log(`%c👥 Detected ${userList.length} Notion accounts:`, 'font-size:13px;font-weight:bold');
      console.log('');
      userList.forEach(([uid, u], i) => {
        const active = uid === cookieUserId ? ' ← currently active' : '';
        console.log(`%c  [${i}]  ${u.name || '(unknown)'} ${u.email ? '(' + u.email + ')' : ''}${active}`, 'font-size:13px');
      });
      console.log('');
      console.log('%c👆 See the account list above. A prompt will appear in 3 seconds...', 'color:#ff9800;font-size:12px');

      await new Promise(resolve => setTimeout(resolve, 3000));

      const promptText = userList.map(([uid, u], i) => {
        const active = uid === cookieUserId ? ' ← current' : '';
        return `[${i}] ${u.name || '(unknown)'} ${u.email ? '(' + u.email + ')' : ''}${active}`;
      }).join('\n');

      const idx = prompt(`Select the account to extract:\n\n${promptText}\n\nEnter number (0 ~ ${userList.length - 1}):`);
      if (idx === null || idx.trim() === '') {
        console.log('%c⚠️ Cancelled', 'color:#ff9800');
        return;
      }
      const chosen = userList[parseInt(idx)];
      if (!chosen) {
        console.error(`❌ Number "${idx}" is invalid`);
        return;
      }
      chosenUserId = chosen[0];
      chosenUserName = chosen[1].name;
      chosenUserEmail = chosen[1].email;
    }

    console.log(`%c✅ Selected user: ${chosenUserName || chosenUserId.slice(0,8)} ${chosenUserEmail ? '(' + chosenUserEmail + ')' : ''}`, 'color:#00c853;font-size:13px');

    // ─── Select workspace ───
    if (spaceList.length === 0) {
      console.error('❌ No workspaces found.');
      return;
    }

    console.log('');
    console.log(`%c📂 Found ${spaceList.length} workspace(s):`, 'font-size:13px;font-weight:bold');
    console.log('');
    spaceList.forEach((s, i) => {
      const label = s.name || `(ID: ${s.space_id.slice(0, 13)}...)`;
      const planStr = s.plan ? `  Plan: ${s.plan}` : '';
      console.log(`%c  [${i}]  ${label}${planStr}`, 'font-size:13px');
    });

    let chosenSpace;
    if (spaceList.length === 1) {
      chosenSpace = spaceList[0];
      console.log('%c🎯 Only one workspace found, auto-selecting', 'color:#2196f3;font-weight:bold');
    } else {
      console.log('');
      console.log('%c👆 A prompt will appear in 3 seconds to select a workspace...', 'color:#ff9800;font-size:12px');
      await new Promise(resolve => setTimeout(resolve, 3000));

      const promptText = spaceList.map((s, i) => {
        const label = s.name || `ID: ${s.space_id.slice(0, 13)}...`;
        return `[${i}] ${label}`;
      }).join('\n');

      const idx = prompt(`Select the workspace with AI access:\n\n${promptText}\n\nEnter number (0 ~ ${spaceList.length - 1}):`);
      if (idx === null || idx.trim() === '') {
        console.log('%c⚠️ Cancelled', 'color:#ff9800');
        return;
      }
      chosenSpace = spaceList[parseInt(idx)];
      if (!chosenSpace) {
        console.error(`❌ Number "${idx}" is invalid`);
        return;
      }
    }

    // ─── Output result ───
    const account = {
      token_v2: 'YOUR_TOKEN_V2',
      space_id: chosenSpace.space_id,
      user_id: chosenUserId,
      space_view_id: chosenSpace.space_view_id,
      user_name: chosenUserName,
      user_email: chosenUserEmail
    };

    const json = JSON.stringify(account, null, 2);
    const spaceLabel = chosenSpace.name || chosenSpace.space_id.slice(0, 13) + '...';

    console.log('');
    console.log('%c═══════════════════════════════════════════════', 'color:#00c853');
    console.log(`%c✅ User: ${chosenUserName || '(unknown)'}  Workspace: ${spaceLabel}`, 'color:#00c853;font-weight:bold;font-size:14px');
    console.log('%c═══════════════════════════════════════════════', 'color:#00c853');
    console.log('');
    console.log(json);
    console.log('');
    console.log('%c⚠️  Next step: replace YOUR_TOKEN_V2 with the token_v2 value you copied', 'color:#ff9800;font-weight:bold');
    console.log('%c   Then paste it into the accounts.json array', 'color:#ff9800');
    console.log('%c   ⚠️  Note: token_v2 must be from the account you selected! Confirm in Cookies', 'color:#ff9800');

    setTimeout(() => {
      navigator.clipboard.writeText(json)
        .then(() => console.log('%c📋 Copied to clipboard automatically', 'color:#00c853'))
        .catch(() => console.log('%c📋 Please manually select and copy the JSON above', 'color:#ff9800'));
    }, 800);

  } catch (e) { console.error('❌ Extraction failed:', e.message) }
})();
