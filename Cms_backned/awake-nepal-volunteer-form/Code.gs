/**
 * Awake Nepal — Volunteer Registration backend
 * Paste this whole file into Google Apps Script (script.google.com)
 * attached to a Google Sheet, then deploy as a Web App.
 */

const SHEET_NAME = 'Responses';

const HEADERS = [
  'Timestamp',
  'Full Name',
  'Phone Number',
  'Email',
  'Age',
  'Gender',
  'District & Province',
  'Education Level',
  'Volunteer Areas',
  'Why Join',
  'Previous Experience',
  'Experience Detail',
  'Available 1 Week in Chitwan',
  'Can Travel to Chitwan',
  'Skills',
  'Participated Before',
  'Anything Else',
  'Declaration Confirmed'
];

function getSheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) sheet = ss.insertSheet(SHEET_NAME);
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(HEADERS);
    sheet.getRange(1, 1, 1, HEADERS.length)
      .setFontWeight('bold')
      .setBackground('#d62828')
      .setFontColor('#ffffff');
    sheet.setFrozenRows(1);
  }
  return sheet;
}

function doPost(e) {
  try {
    const d = JSON.parse(e.postData.contents);
    const sheet = getSheet_();
    sheet.appendRow([
      new Date(),
      d.fullName || '',
      "'" + (d.phone || ''),   // leading apostrophe keeps phone as text
      d.email || '',
      d.age || '',
      d.gender || '',
      d.district || '',
      d.education || '',
      d.areas || '',
      d.whyJoin || '',
      d.experience || '',
      d.experienceDetail || '',
      d.availableWeek || '',
      d.canTravel || '',
      d.skills || '',
      d.participatedBefore || '',
      d.anythingElse || '',
      d.declaration || ''
    ]);
    return ContentService
      .createTextOutput(JSON.stringify({ status: 'success' }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ status: 'error', message: String(err) }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

// Optional: visiting the web app URL in a browser shows a friendly message
function doGet() {
  return ContentService.createTextOutput(
    'Awake Nepal Volunteer Form API is running ✔'
  );
}
