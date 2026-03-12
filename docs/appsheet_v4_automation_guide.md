# AppSheet Automation 設定ガイド (v4.0 準拠)

本ガイドは、業務の「漏れ」を防ぎ、PDCAを加速させるための自動通知 Bot の設定を定義します。

---

## 📬 1. 見積フォロー Bot (営業支援)

**目的**: 見積を提出してから 7日以上音沙汰がない案件をリマインド。

1. **Event**: `Schedule` (Daily)
2. **Filter Condition**:
   ```appsheet
   AND(
     [ステータス] = "見積提出済",
     DAYS(TODAY(), MAX(Related Papers[発行日])) >= 7
   )
   ```
3. **Action**: `Send a notification`
   - `Recipient`: `[自社担当者ID].[メール]`
   - `Message`: `「[案件名]」の見積提出から7日が経過しました。状況を確認し、フォローをお願いします。`

---

## 📑 2. 承認図催促 Bot (納期管理)

**目的**: 発注したのにメーカーから図面が来ない（承認図確定していない）案件をリマインド。

1. **Event**: `Schedule` (Daily)
2. **Filter Condition**:
   ```appsheet
   AND(
     [大分類] = "工具販売",
     [小分類] = "受注生産",
     [ステータス] = "受注・発注済",
     DAYS(TODAY(), [発生日]) >= 21
   )
   ```
3. **Action**: `Send an email` (to Supplier/Person)
   - `Message`: `[案件名] について、承認図面が未送付となっております。ご確認をお願いします。`

---

## 🛠️ 3. 研磨回数アラート Bot (リピート提案)

**目的**: 工具が限界（寿命）に近づいた時に、再製作を提案。

1. **Event**: `T6_WorkLogs` に Add された時
2. **Condition**:
   ```appsheet
   [個体ID].[累計研磨回数] >= LOOKUP("研磨回数アラート閾値", "M4_Settings", "設定キー", "設定値")
   ```
3. **Action**: `Send a notification` (to Sales)
   - `Message`: `個体 [個体ID] が規定の研磨回数に達しました。リピート製作の提案を検討してください。`

---

## 💰 4. 20日締め請求リマインド Bot (経理支援)

**目的**: 納品済みだが請求書が発行されていない案件をピックアップ。

1. **Event**: `Schedule` (Monthly, 18th day)
2. **Filter Condition**:
   ```appsheet
   AND(
     [ステータス] = "納品済",
     COUNT(SELECT(T2_Papers[帳票ID], AND([案件ID]=[_THISROW].[案件ID], [種別]="請求書"))) = 0
   )
   ```
3. **Action**: `App: go to another view` (Dashboard URL)
   - `Message`: `今月の20日締め対象で、請求書未発行の案件が [n] 件あります。確認してください。`

---

## 📡 5. [上級者向け] ステータス自動遷移用 Webhook 連携

第4フェーズの GAS と連携する場合、「PDF生成完了後」に AppSheet 側へステータス更新を通知する Webhook を設定します。

- **Endpoint**: AppSheet API
- **Body**: `{ "Action": "Edit", "Rows": [{ "案件ID": "...", "ステータス": "納品済" }] }`
