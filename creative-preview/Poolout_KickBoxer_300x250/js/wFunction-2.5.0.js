/***********
**Function**
***********/
var crossBrowser = [
    'Transition',
    'Transform',
    'BackfaceVisibility',
    'animation'
];

/* Check user browser */
var UserBrowser = {
    isChrome: function() {
        if(/Chrome/.test(navigator.userAgent) && /Google Inc/.test(navigator.vendor)) {
            return true;
        } else {
            return false;
        }
    },
    isFireFox: function() {
        if(navigator.userAgent.toLowerCase().indexOf('firefox') > -1) {
            return true;
        } else {
            return false;
        }
    },
    isMsie: function() {
        if(window.navigator.userAgent.indexOf("MSIE ") > 0 || !!navigator.userAgent.match(/Trident.*rv\:11\./)) {
            return true;
        } else {
            return false;
        }
    },
    isSafari: function() {
        if(navigator.vendor && navigator.vendor.indexOf('Apple') > -1) {
            return true;
        } else {
            return false;
        }
    },
    isMac: function() {
        if(navigator.appVersion.indexOf("Mac")!=-1) {
            return true;
        } else {
            return false;
        }
    },
    isMobile: function() {
        if(/iPhone|iPad|iPod|Android/i.test(navigator.userAgent)) {
            return true;
        } else {
            return false;
        }
    }
};

/****************
**Miscellaneous**
****************/
var addRemoveClass = function(aClass, aTarget, cItem) {
    for(var i = 0; i < aTarget.length; i++) {
        var elem = document.getElementById(aTarget[i])

        for(var j = 0; j < cItem.length; j++) {
            var makeClass = aClass?'add':'remove';

            elem.classList[makeClass](cItem[j]);
        }
    }
};

var insertStyle = function(aTarget, sProp, sValue) {
    var cBrowser = false;
    var ctr;

    for(var i = 0; i < crossBrowser.length; i++) {
        if(sProp.toUpperCase().replace("-", "") == crossBrowser[i].toUpperCase()) {
            cBrowser = true;
            ctr = i;
        }
    }

    if(cBrowser) {
        if(crossBrowser[ctr] == 'Transition') {
            var val = sValue.toUpperCase();
            var noCrossBrowser = true;

            for(var i = 0; i < crossBrowser.length; i++) {
                var n = val.search(crossBrowser[i].toUpperCase());

                if(n!=-1) {
                    aTarget.style[crossBrowser[ctr].toLowerCase()] = sValue;
                    aTarget.style['webkit' + crossBrowser[ctr]] = sValue.slice(0, n) + '-webkit-' + sValue.slice(n, (sValue.length));
                    aTarget.style['moz' + crossBrowser[ctr]] = sValue.slice(0, n) + '-moz-' + sValue.slice(n, (sValue.length));
                    aTarget.style['o' + crossBrowser[ctr]] = sValue.slice(0, n) + '-o-' + sValue.slice(n, (sValue.length));
                    aTarget.style['ms' + crossBrowser[ctr]] = sValue.slice(0, n) + '-ms-' + sValue.slice(n, (sValue.length));

                    noCrossBrowser = false;
                }
            }

            if(noCrossBrowser) {
                aTarget.style[sProp] = sValue;
            }
        } else {
            aTarget.style[crossBrowser[ctr].toLowerCase()] = sValue;
            aTarget.style['webkit' + crossBrowser[ctr]] = sValue;
            aTarget.style['moz' + crossBrowser[ctr]] =  sValue;
            aTarget.style['o' + crossBrowser[ctr]] =  sValue;
            aTarget.style['ms' + crossBrowser[ctr]] =  sValue;
        }
    } else {
        aTarget.style[sProp] = sValue;
    }
};

/****************
**Main Function**
****************/
var customElement = function(arrayTarget) {
    /* Add class to the element */
    this.addClass = function(inClass) {
        var ic = inClass.split(" ");

        addRemoveClass(true, arrayTarget, ic);
    };

    /* Remove class to the element */
    this.removeClass = function(outClass) {
        var oc = outClass.split(" ");

        addRemoveClass(false, arrayTarget, oc);
    };

    /* Change style of the element */
    this.changeStyle = function(sProperty, sValue) {
        var splitProp = sProperty.split(";");
        var splitValue = sValue.split(";");

        if(splitProp.length == splitValue.length) {
            for(var i = 0; i < arrayTarget.length; i++) {
                var elem = document.getElementById(arrayTarget[i])

                for(var j = 0; j < splitProp.length; j++) {
                    insertStyle(elem, splitProp[j], splitValue[j]);
                }
            }
        } else {
            throw 'Error properties and values in ' + arrayTarget + ' are not equal.';
        }
    };
};

var w = function(eid) {
    var splitTarget = eid.split(" ");

    for(var i = 0; i < splitTarget.length; i++) {
        var x = document.getElementById(splitTarget[i]);

        if(x == null) {
            throw 'Error ' + splitTarget[i] + ' is not defined. Make sure the ID is exist';
        }
    }

    var arrX = new customElement(splitTarget);

    return arrX;
};

/* Scroll move */
var wScrollConfig = {
    barId: '',
    barX: 0,
    barUp: 0,
    barDown: 0,
    contentId: '',
    contentX: 0,
    contentUp: 0,
    contentDown: 0,
    contentBarDeduction: 0,
    contentDeduction: 0,
    contentContainerId: ''
};

var wScrollProperties = {
    ratio: 0,
    newBarY: 0,
    newContentY: 0,
    lastScrollY: 0,
    scrollDirection: 0,
    multiplier: 1,
    initialize: false
};

var wInitScroll = function() {
    var sbId = document.getElementById(wScrollConfig.barId);
    var icId = document.getElementById(wScrollConfig.contentContainerId);

    sbId.addEventListener('mousedown', wHoldScroll);
    sbId.addEventListener('touchstart', wHoldScroll);
    window.addEventListener('mouseup', wReleaseScroll);
    window.addEventListener('touchend', wReleaseScroll);
    icId.addEventListener('wheel', wScrollMove);
    icId.addEventListener('mousedown', wHoldScroll);
    icId.addEventListener('touchstart', wHoldScroll);

    wScrollProperties.lastScrollY = wScrollProperties.barUp;
    wScrollProperties.newBarY = wScrollConfig.barUp
    wScrollProperties.newContentY = wScrollConfig.contentUp
    wScrollProperties.ratio = (wScrollConfig.contentDown - wScrollConfig.contentUp) / (wScrollConfig.barDown - wScrollConfig.barUp);

    wScrollProperties.initialize = true;
}

var GetPosition = function(e) {
    var sd;
    if(UserBrowser.isMobile()) {
        try {
            if(e.target.id == wScrollConfig.barId) {
                sd = event.touches[0].pageY;
            } else {
                sd = event.touches[0].pageY * -1;
            }
        } catch(e) {
            event.preventDefault();
        }
    } else {
        sd = e.clientY;
    }
    return sd;
}

var wHoldScroll = function(e) {
    wScrollProperties.lastScrollY = GetPosition(e);
    if(UserBrowser.isMobile()) {
        window.addEventListener('touchmove', wScrollMove);
    } else {
        window.addEventListener('mousemove', wScrollMove);

        // Disabled highligh when holding the scroll bar
        if(e.target.id == wScrollConfig.barId) {
            var iriMId = document.getElementById('IRI_mainContainer');

            iriMId.style['userSelect'] = 'none';
            iriMId.style['webkitUserSelect'] = 'none';
            iriMId.style['mozUserSelect'] =  'none';
            iriMId.style['oUserSelect'] =  'none';
            iriMId.style['msUserSelect'] =  'none';
        }
    }
}
var wReleaseScroll = function() {
    if(UserBrowser.isMobile()) {
        window.removeEventListener('touchmove', wScrollMove);
    } else {
        window.removeEventListener('mousemove', wScrollMove);

        var iriMId = document.getElementById('IRI_mainContainer');

        iriMId.style['userSelect'] = 'auto';
        iriMId.style['webkitUserSelect'] = 'auto';
        iriMId.style['mozUserSelect'] =  'auto';
        iriMId.style['oUserSelect'] =  'auto';
        iriMId.style['msUserSelect'] =  'auto';
    }
}

var wScrollMove = function(e) {
    if(wScrollProperties.initialize) {
        var canMove = false;
        var lastNewDiff = 0;

        if(e.type == 'wheel') {
            if(e.deltaY < 0) {
                wScrollProperties.lastScrollY = 1;
                wScrollProperties.scrollDirection = 0;
            } else {
                wScrollProperties.lastScrollY = 0;
                wScrollProperties.scrollDirection = 1;
            }
        } else {
            wScrollProperties.scrollDirection = GetPosition(e);
        }

        if(wScrollProperties.lastScrollY < wScrollProperties.scrollDirection) {

            if(wScrollConfig.barDown >= wScrollProperties.newBarY) {
                console.log('Scroll Going Down');

                if (wScrollConfig.contentBarDeduction > 0 && wScrollConfig.contentDeduction > 0) {
                    lastNewDiff = (wScrollProperties.scrollDirection - wScrollProperties.lastScrollY) * wScrollConfig.contentBarDeduction;
                    wScrollProperties.newBarY+=lastNewDiff;
                    wScrollProperties.newContentY+=parseInt(((lastNewDiff * wScrollProperties.ratio) * -1)) - wScrollConfig.contentDeduction;
                    console.log('Deduction is Active!');
                    console.log('Content Sum:', parseInt(((lastNewDiff * wScrollProperties.ratio) * -1)) - wScrollConfig.contentDeduction);
                } else {
                    lastNewDiff = wScrollProperties.scrollDirection - wScrollProperties.lastScrollY;
                    wScrollProperties.newBarY+=lastNewDiff;
                    wScrollProperties.newContentY+=parseInt(((lastNewDiff * wScrollProperties.ratio) * -1));
                    console.log('Content Sum:', parseInt(((lastNewDiff * wScrollProperties.ratio) * -1)));
                }

                console.log('Content Bar Sum:',lastNewDiff);
                console.log('Content Total:', wScrollProperties.newContentY);

                if(wScrollProperties.newBarY > wScrollConfig.barDown) {
                    wScrollProperties.newBarY = wScrollConfig.barDown;
                    wScrollProperties.newContentY = wScrollConfig.contentDown * -1;
                }
                canMove = true;
            }
        } else if(wScrollProperties.lastScrollY > wScrollProperties.scrollDirection) {

            if(wScrollConfig.barUp <= wScrollProperties.newBarY) {
                console.log('Scroll Going Up');

                if (wScrollConfig.contentBarDeduction > 0 && wScrollConfig.contentDeduction > 0) {
                    lastNewDiff = (wScrollProperties.lastScrollY - wScrollProperties.scrollDirection) * wScrollConfig.contentBarDeduction;
                    wScrollProperties.newBarY-=lastNewDiff;
                    wScrollProperties.newContentY+=parseInt((lastNewDiff * wScrollProperties.ratio)) + wScrollConfig.contentDeduction;
                    console.log('Deduction is Active!');
                    console.log('Content Sum:', parseInt((lastNewDiff * wScrollProperties.ratio)) + wScrollConfig.contentDeduction);
                } else {
                    lastNewDiff = wScrollProperties.lastScrollY - wScrollProperties.scrollDirection;
                    wScrollProperties.newBarY-=lastNewDiff;
                    wScrollProperties.newContentY+=parseInt((lastNewDiff * wScrollProperties.ratio));
                    console.log('Content Sum:', parseInt((lastNewDiff * wScrollProperties.ratio)));
                }

                console.log('Content Bar Sum:', lastNewDiff);
                console.log('Content Total:', wScrollProperties.newContentY);

                if(wScrollProperties.newBarY < wScrollConfig.barUp) {
                    wScrollProperties.newBarY = wScrollConfig.barUp;
                    wScrollProperties.newContentY = wScrollConfig.contentUp;
                }
                canMove = true;
            }
        }

        if(canMove) {
            wScrollProperties.lastScrollY = wScrollProperties.scrollDirection;

            w(wScrollConfig.barId).changeStyle('transform',  'translate(' + wScrollConfig.barX + 'px, ' + wScrollProperties.newBarY + 'px)');
            w(wScrollConfig.contentId).changeStyle('transform',  'translate(' + wScrollConfig.contentX + 'px, ' + wScrollProperties.newContentY + 'px)');
        }
    }
}