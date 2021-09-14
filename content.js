const LOAD_DELAY = 10000;
const SOCKET_ADDRESS = "ws://localhost:8700/";
let socket = new WebSocket(SOCKET_ADDRESS);


let observer = new MutationObserver(mutations => {
   myMain()
});

chrome.extension.onMessage.addListener(function(request, sender, response) {
   /* Remove old warning message */
   if (request.message === 'pageLoaded') {
      let old_alert_message = document.getElementById("FaceCheck_alert");
      if (old_alert_message) {
         old_alert_message.parentElement.removeChild(old_alert_message);
      }
      setTimeout(() => {  myMain(); }, LOAD_DELAY);
   }
})

function myMain() {
   let profileName = getProfileName();
   
   if (!profileName) {
      profileName = null;
      console.log("Profile name could not be found");
   } 

   let profilePicElement = getProfilePictureElement();
   // Couldn't find profile image therefore tell user no info could be found
   if (!profilePicElement) {
      console.log("nooo");
      displayNoInfoAlert();
      return;
   }
   profilePicURL = getImageURL(profilePicElement);
   // Couldn't extract profile image url therefore tell user no info could be found
   if (profilePicURL == null) {
      console.log("nooo");
      profilePicElement.style.border = '7px solid yellow';
      displayNoInfoAlert()
      return;
   }

   message = {
      "name": profileName,
      "image_url" : profilePicURL
   };
   console.log(JSON.stringify(message));

   try {
      socket.send(JSON.stringify(message));
   }
   catch(err) {
      console.log("Could not connect to server" + err);
      return;
   }
   socket.onmessage = function(event) {
      console.log(event.data);
      if (event.data.includes("occurrences")) {
         profilePicElement.style.border = '7px solid green';
      }

      else if (event.data.includes("WARNING")) {
         profilePicElement.style.border = '7px solid red';
      }
   
      else if (event.data.includes("couldn't")) {
         profilePicElement.style.border = '7px solid yellow';
      }
      
      document.body.insertAdjacentHTML('beforeend', event.data);
   }

};

socket.onclose = function(event) {
   if (event.wasClean) {
      console.log(`[close] Connection closed cleanly, code=${event.code} reason=${event.reason}`);
   } else {
      console.log('[close] Connection died');
   }
 };
 socket.onerror = function(error) {
   console.log(`[error] ${error.message}`);
 };



function displayNoInfoAlert() {
   fetch(chrome.runtime.getURL('index.html')).then(r => r.text()).then(html => {
      document.body.insertAdjacentHTML('beforeend', html);
   });
}

function getProfileName() {
   var nameElementsOnPage = document.querySelectorAll('[class*="name" i]', '[class$="name" i]', '[class^="name" i]');
   let largestFontSize = 0;
   let profileName;
   nameElementsOnPage.forEach(element => {
      elementFontSize = getFontSize(element);
      if (element.innerHTML.length != 0 && elementFontSize > largestFontSize) {
         profileName = element.innerHTML;
         largestFontSize = elementFontSize;
      }
   });
   if (profileName) {
      return profileName
   }
   return null;
}

function getProfileNameElement() {
   var nameElementsOnPage = document.querySelectorAll('[class*="name" i]', '[class$="name" i]', '[class^="name" i]');
   let largestFontSize = 0;
   let profileNameElement;
   nameElementsOnPage.forEach(element => {
      elementFontSize = getFontSize(element);
      if (element.innerHTML.length != 0 && elementFontSize > largestFontSize) {
         profileNameElement = element;
         profileName = element.innerHTML;
         largestFontSize = elementFontSize;
      }
   });
   return profileNameElement;
}

function getFontSize(element) {
   return parseInt(window.getComputedStyle(element).fontSize, 10);
}

/* Get largest image on page */
function getProfilePictureElement() {
   // Gather all elements which could be images
   var imagesOnPage = document.querySelectorAll(
   '[class*="photo" i], [class$="photo" i], [class^="photo" i], [class*="image" i], [class$="image" i], [class^="image" i], [style*=url], img,  img.src,  [class*=picture]'); /* make so start end and middle for each */
  
   let maxSize = 0;
   let profilePic;
   imagesOnPage.forEach(element => {
      let pictureArea = getElementArea(element);  
         if ((pictureArea > maxSize) && element.childNodes.length == 0 && element.getAttribute("id") != "bgImgBox" && element.getAttribute("class") != "microProfil") {
            maxSize = pictureArea;
            profilePic = element;
         }
   });
   return profilePic;
};

function getImageURL(element) {
   let url = element.getAttribute("src");
   if (url == null) {
      url = element.getAttribute("style");
      if (url != null) {
         url = url.match(/url\(["']?([^"']*)["']?\)/)[1];
      }
   }
   return url;
}

function getElementArea(element) {
   return element.offsetHeight * element.offsetWidth;
};

// taken from https://gist.github.com/colxi/c9ab898aa063e0943d4fae1840b982d8

