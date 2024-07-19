function onOpen() {
  var ui = SpreadsheetApp.getUi();
  ui.createMenu('Custom Menu')
      .addItem('Start Script', 'startScrapeAndMonitor')
      .addToUi();
}

function doPost(e) {
  // try{
    let ss = SpreadsheetApp.getActiveSpreadsheet();
    let shLog = ss.getSheetByName("Logs")
    shLog.appendRow([new Date(),JSON.stringify(e)])
  
    let data =JSON.parse(e.postData.contents)
    if(data.uniqueID){
      updateData(data)
    }

  // }
  // catch(err){
  //   console.log(err)
  // }
  
  
  return ContentService.createTextOutput(`{"status":"true"}`).setMimeType(ContentService.MimeType.JSON)


}

function updateData(data){
  let ss = SpreadsheetApp.getActiveSpreadsheet();
  let shData=ss.getSheetByName("Data");
  shData.getRange(data.uniqueID,4,1,2).setValues([["In Progress",data.supplier_name]])
  SpreadsheetApp.flush();
}

function startScrapeAndMonitor(){
  let ss = SpreadsheetApp.getActiveSpreadsheet();
  let baseURL= ss.getRange('scriptURL').getValue();
  let apiKey= ss.getRange('apiKey').getValue();
  let shData=ss.getSheetByName("Data");
  let productData = shData.getRange(2,1,shData.getLastRow()-1,3).getValues();





  // make API call payload
  let pendingData=productData //.filter(itm => itm[2]=="");
  let payload = {
                  "apiKey":apiKey,
                  "products":pendingData
                };
  let options = {
                  "method": "POST",
                  "url":`${baseURL}send_data`,
                  "payload": JSON.stringify(payload),
                  "muteHttpExeptions": true,
                  "headers": {
                  "Content-Type": "application/json",
                  }
                }              

  let resp = UrlFetchApp.fetch(options.url,options);
  let respTxt = resp.getContentText();
  let respData=JSON.parse(respTxt);



  let tt=0

}


function addData() {
    let ss=SpreadsheetApp.getActiveSpreadsheet();
    let sh=ss.getSheetByName("Data");

    let data=[
        [
            "https://m.media-amazon.com/images/I/513H5yrRU0L.jpg",
            "smaate 3D Screen Protector Compatible with P66D 1.85\u201d Nerunsa Ddidbi Dotn and Aptkdoe Smart Watch"
        ],
        [
            "https://m.media-amazon.com/images/I/518OMbTC7hL.jpg",
            "Valuetoner 260XL and 261XL Ink Cartridges Combo Pack Replacement for Canon 260 and 261 Ink Cartridges PG-260 CL-261 Work with Canon TS6420a TS6420 TS6400 TR7020 TR7020a TS5320 (1 Black, 1 Tri-Color)"
        ],
        [
            "https://m.media-amazon.com/images/I/21fXCH0odPL.jpg",
            "Single Replacement L Earbud for AirPods Pro 1st Generation with Detachable Ear Hooks Left Ear Side"
        ],
        [
            "https://m.media-amazon.com/images/I/31rSOpdAqVL.jpg",
            "Anicell 6 Pack Filters Replacement for Shark Navigator Deluxe NV42, NV4226, NV46, NV44, NV4626, UV402, UV410, NV36 Upright Vacuum, Part #XFF36"
        ],
        [
            "https://m.media-amazon.com/images/I/3136JOX5+UL.jpg",
            "Ceiling Fan Remote Control Replacement for Hampton Bay Hunter UC7078T CHQ7078T CHQ8BT7078T L3H2003FANHD Fan-HD Fan-HD6 RR7078TR, with Reverse"
        ],
        [
            "https://m.media-amazon.com/images/I/51A7mQ41xxL.jpg",
            "Compatible Oven Igniter for LG LRG3095ST, LRG3095SB, LRG3095SW Range Models"
        ],
        [
            "https://m.media-amazon.com/images/I/51dbnllAV1L.jpg",
            "17'' T4 16W Warm White Fluorescent Bulb Replacement Furnlite FC-952 Light,Westek 20125 - FA200WBC,16 Watt 120V Linear 3000K FC-953,G5 Base (3 Pack)"
        ],
        [
            "https://m.media-amazon.com/images/I/717tPHjYQHL.jpg",
            "Gutenberg's tough tea filter bags 10-100 Packs | nylon filter bags | All Micron Sizes (10-Pack, 37)"
        ],
        [
            "https://m.media-amazon.com/images/I/7133qhpDw7L.jpg",
            "56 Pack Motorcycle Battery Terminal Nuts and Bolt Kit M6 x 10 mm 12 mm 16 mm 20 mm Bolt Square Nut Kit Stainless Steel Motorcycle Battery Screw and Nut - Perfect for ATV Bike Scooter"
        ],
        [
            "https://m.media-amazon.com/images/I/61P+gQ7ag+L.jpg",
            "2024 Newest Digital Converter Box for TV, OWERSLYN [ATSC Tuner Hidden Behind The TV], TV Recording&Playback, USB Media Player, TV Tuner with 1080P HDMI/AV Output, Timer Setting, 2-in-1 Remote"
        ],
        [
            "https://m.media-amazon.com/images/I/71RKZDcn2JL.jpg",
            "CR8GR8 4 Professional Hair Clipper Guards Cutting Guides Fits for Manscaper 3.0 with Organizer, Fit for The Lawn Mower 3.0 Clipper Combs Replacement - 1/8\" to 1/2\" inch"
        ],
        [
            "https://m.media-amazon.com/images/I/81J9VqcbhnL.jpg",
            "Nicpro 30PCS Black Metal Mechanical Pencils Set in Leather Case, Art Drafting Pencil 0.5, 0.7, 0.9 mm, 2mm Lead Pencil Holders for Sketching Drawing With 16 Tube (6B 4B 2B HB 2H 4H Colors)Lead Refills"
        ],
        [
            "https://m.media-amazon.com/images/I/61HcyEnCMDL.jpg",
            "338906 Gas Dryer Flame Sensor 279834 Gas Valve Solenoid Coils 279311 Igniter Kit - Gas Dryer Repair Kit - Fit for Whirlpool Ken-More Dryers - Replaces WP338906 AP3094251 PS334310-1 Year Warranty"
        ],
        [
            "https://m.media-amazon.com/images/I/51eZ0wOFnFL.jpg",
            "Adjustable Bed Richmat HJH55 Remote Control Replacement"
        ],
        [
            "https://m.media-amazon.com/images/I/61+ERfxRldL.jpg",
            "Delta Faucet 72030-CZ Disposal and Flange Stopper, Kitchen, Champagne Bronze, 4.50 x 4.50 x 4.50 inches"
        ],
        [
            "https://m.media-amazon.com/images/I/717eT2qsTfL.jpg",
            "ST Action Pro 9mm Orange Safety Trainer Dummy Round 10 Rounds"
        ],
        [
            "https://m.media-amazon.com/images/I/81oeGM-lZ6L.jpg",
            "Hasanbar Stove Cover Gas Stove Top Burner Covers Protectors for Samsung Gas Range Stove Mat Protector Reusable, Oven Liners Mat Gas Range Protectors Covers, Stove Guard Non-Stick Washable"
        ],
        [
            "https://m.media-amazon.com/images/I/71YqrS4rGML.jpg",
            "Remote Control UC7225T (7225) with Wall Holder by MFP"
        ],
        [
            "https://m.media-amazon.com/images/I/71SO7YvZDDL.jpg",
            "Goodman Janitrol Amana Furnace Igniter Ignitor B1401018S B1401018 B14010-18"
        ]
    ]

    sh.getRange(2,1,data.length,data[0].length).setValues(data);
    SpreadsheetApp.flush();


}
