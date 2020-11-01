# Receive and read emails with XPath 3.1!

[TL;DR](#enter-xpath-awesomeness)

This is inspired by [this HN thread](https://news.ycombinator.com/item?id=24941663), which links to [this blog post](https://tomforb.es/xcat-1.0-released-or-xpath-injection-issues-are-severely-underrated/) that introduced yours truly to the "awesomeness" of XPath 2.0/3.1. In that HN thread folks were wondering whether you can receive email with XPath.

Wonder no more. Or wonder instead whether any XPath 3.1 implementation contains an ad hoc, informally-specified, bug-ridden, slow implementation of half of Common Lisp.

Here I demonstrate how you can receive and read your emails on Gmail/G Suite (wait, I forgot it's been rebranded as Google Workplace and infinite Drive storage is gone; fuck it, I'll remain grandfathered and call it G Suite) with XPath, through Gmail's REST API. I'm not sure if you can do JMAP with XPath (didn't check if JMAP allows GET without special headers), and you probably can't do IMAP/POP3 with XPath (for now; there's always the next version, solving the current version's pain points). But let's just pretend you've sold your <s>soul</s>emails to Google, like I've done.

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->


- [Caveats](#caveats)
- [Preparations](#preparations)
  - [Software dependencies](#software-dependencies)
  - [Acquiring a Gmail access token](#acquiring-a-gmail-access-token)
- [Enter XPath awesomeness](#enter-xpath-awesomeness)
- [Further reading](#further-reading)
- [License](#license)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Caveats

- Only works for Gmail/G Suite.

- I only tested the process and the code on my G Suite account. There's a chance you need to tweak a few nobs for a Gmail account.

- We acquire (and refresh, if necessary) the Gmail API access token using Google's afficial Python binding, just to get one boring thing out of the way. Gotta say interactivity isn't XPath's strong suite.

- I'm cheating a little by passing the access token as a URL paramter instead of in the Authorization header, a legacy feature which according to [Google API docs](https://developers.google.com/identity/protocols/oauth2) will be deprecated on June 1st, 2021. I don't think XPath 3.1 allows custom headers in its document-retrieving functions.

- I have only used XPath 1.0 to a limited extent (i.e. selecting nodes) before being introduced to the awesomeness of XPath 2.0/3.1 by the linked blog post. I consulted the specs https://www.w3.org/TR/xpath-31/ and https://www.w3.org/TR/xpath-functions-31/ while writing the code, without reading them in whole. So forget idiomatic code. I might even have missed awesome features that could make the code more succint.

## Preparations

### Software dependencies

The following instructions were prepared for Ubuntu 20.04 (of course, only the apt invocation is platform specific).

```console
$ git clone https://github.com/clopen/xpath-receive-email
$ cd xpath-receive-email
$ apt install libxml-libxml-perl openjdk-13-jre python3 python3-venv
$ python3 -m venv venv
$ . venv/bin/activate
$ pip install google_auth_oauthlib
```

### Acquiring a Gmail access token

You need to register and configure a Google API project to use the Gmail API.

- Head over to the [Google API Console](https://console.developers.google.com/apis/dashboard) and add your project;
- Enable the Gmail API;
- During OAuth consent screen configuration, enable the `https://www.googleapis.com/auth/gmail.readonly` scope (maybe also the non-sensitive scope `https://www.googleapis.com/auth/userinfo.email`, not sure if needed but why the hell not let you view your own email address);
- Go to "Credentials" screen and generate a new OAuth client ID for the "Desktop" type;
- Click the download button next to your newly created client entry to download your client credentials as a JSON file;
- Move the .json file into your working directory and rename to `client.json`;

Now, you can run

```console
$ python3 auth.py
```

and follow the flow (the standard OAuth flow, which requires you to go to the auth URL in a browser and authorize) to generate your access token. It will be saved alongside the refresh token and friends in `credentials.json`. The preparation is complete.

In the future, when the access token expires, run `python3 auth.py` again to refresh the token (without the need to reauthorize).

## Enter XPath awesomeness

With the legwork done, it's time for XPath to do its magic.

Surprisingly, there seem to be very few implementations of the awesome query language that is XPath 3.1. I found three in some W3C report (which I somehow can't find anymore): [Saxon](https://www.saxonica.com/documentation/#!conformance/xpath31), a Java library; [XmlPrime](https://www.xmlprime.com/xmlprime/index.htm), a .NET library; and [BaseX](https://basex.org/), some DB engine. Someone wrote a less daunting CLI wrapper, [saxon-lint](https://github.com/sputnick-dev/saxon-lint) (similar to xmllint) for Saxon HE, so I decided to unleash the power of XPath 3.1 with that. saxon-lint ships with an outdated version of Saxon that doesn't support XPath 3.0 though, so I patched it a bit and included the patched version as well as the .jar for Saxon-HE in this repo.

The XPath code we use is stored in [`gmail.xpath`](gmail.xpath). I reproduce the code here for readers who can't bother to navigate:

```xquery
declare namespace array = "http://www.w3.org/2005/xpath-functions/array";
declare namespace map = "http://www.w3.org/2005/xpath-functions/map";

(: Begin configuration options :)
(: See https://developers.google.com/gmail/api/reference/rest/v1/users.messages/list :)
let $user_id := "me"
let $max_results := 5
let $query := "is:unread"
let $page_token := ""
(: End configuration options :)

let $base64url_decode := function ($encoded) {
  let $codepoint_to_binary := function ($cp) {
    (: A-Z -> 0-25 :)
    if ($cp >= 65 and $cp <= 90) then $cp - 65
    (: a-z -> 26-51 :)
    else if ($cp >= 97 and $cp <= 122) then $cp - 71
    (: 0-9 -> 52-61 :)
    else if ($cp >= 48 and $cp <= 57) then $cp + 4
    (: - -> 62 :)
    else if ($cp = 45) then 62
    (: _ -> 63 :)
    else if ($cp = 95) then 63
    else error(QName("http://localhost", "invalid-base64-character"))
  }

  let $decode_4char_block := function ($c1, $c2, $c3, $c4) {
    (: Store concatenated binary in $buf, and the non-padding length in $binary_len. :)
    let $buf := $codepoint_to_binary($c1)
    let $binary_len := 6
    let $buf := 64 * $buf + $codepoint_to_binary($c2)
    let $binary_len := $binary_len + 6
    (: Character 3 and 4 may be padding =. :)
    let $buf := if ($c3 = 61) then 64 * $buf else 64 * $buf + $codepoint_to_binary($c3)
    let $binary_len := if ($c3 = 61) then $binary_len else $binary_len + 6
    let $buf := if ($c4 = 61) then 64 * $buf else 64 * $buf + $codepoint_to_binary($c4)
    let $binary_len := if ($c4 = 61) then $binary_len else $binary_len + 6
    (: Decode. :)
    let $decoded := [$buf idiv 65536]
    let $buf := $buf mod 65536
    let $decoded := if ($binary_len >= 16) then array:append($decoded, $buf idiv 256) else $decoded
    let $buf := $buf mod 256
    let $decoded := if ($binary_len >= 24) then array:append($decoded, $buf) else $decoded
    return codepoints-to-string($decoded)
  }

  let $input_chars := array { string-to-codepoints($encoded) }
  let $count := array:size($input_chars)
  let $nblocks := ($count + 3) idiv 4
  return string-join(
    for-each((0 to $nblocks - 1), function ($idx) {
      $decode_4char_block(
        $input_chars($idx * 4 + 1),
        $input_chars($idx * 4 + 2),
        $input_chars($idx * 4 + 3),
        $input_chars($idx * 4 + 4)
      )
    }),
    ""
  )
}

let $token := json-doc("credentials.json")("token")

let $filler := function ($char, $len) {
  string-join((1 to $len)!$char)
}

let $filled := function ($content, $char, $len) {
  let $content_len := string-length($content)
  let $left_filler_len := ($len - $content_len - 2) idiv 2
  let $left_filler_len := if ($left_filler_len < 3) then 3 else $left_filler_len
  let $right_filler_len := $len - $content_len - 2 - $left_filler_len
  let $right_filler_len := if ($right_filler_len < 3) then 3 else $right_filler_len
  return $filler($char, $left_filler_len) || " " || $content || " " || $filler($char, $right_filler_len)
}

let $get_individual_message := function ($message_id) {
  let $extract_header := function ($headers, $name) {
    array:for-each($headers, function ($header) {
      if ($header("name") = $name) then $header("value") else ()
    })
  }

  let $url := (
    "https://gmail.googleapis.com/gmail/v1/users/"
    || encode-for-uri($user_id)
    || "/messages/"
    || encode-for-uri($message_id)
    || "?access_token="
    || encode-for-uri($token)
  )
  let $response := json-doc($url)
  let $payload := $response("payload")
  let $headers := $payload("headers")
  return [
    $filler("*", 80),
    "Gmail Message-ID: " || $message_id,
    "Message-ID: " || $extract_header($headers, "Message-ID"),
    "Subject: " || $extract_header($headers, "Subject"),
    "From: " || $extract_header($headers, "From"),
    "To: " || $extract_header($headers, "To"),
    "Date: " || $extract_header($headers, "Date"),
    if (map:contains($payload, "parts"))
    then array:for-each($payload("parts"), function ($part) {
      let $mime := $part("mimeType")
      let $body := $part("body")
      let $size := $body("size")
      return [
        $filled("Part (" || $mime || ")", "-", 80),
        if (map:contains($body, "attachmentId")) then "Attachment (" || $size || " bytes) omitted"
        else if ($mime = "text/html") then "HTML (" || $size || " bytes) omitted"
        else $base64url_decode($part("body")("data"))
      ]
    })
    else [
      $filled("Body", "-", 80),
      $base64url_decode($payload("body")("data"))
    ]
  ]
}

let $get_messages := function () {
  let $url := (
    "https://gmail.googleapis.com/gmail/v1/users/"
    || encode-for-uri($user_id)
    || "/messages?access_token="
    || encode-for-uri($token)
  )
  let $url := $url || "&amp;maxResults=" || $max_results
  let $url := if ($query = "") then $url else ($url || "&amp;q=" || encode-for-uri($query))
  let $url := if ($page_token = "") then $url else ($url || "&amp;pageToken=" || encode-for-uri($page_token))
  let $response := json-doc($url)
  return [
    array:for-each($response("messages"), function ($message) {
      $get_individual_message($message("id"))
    }),
    $filler("*", 80),
    "nextPageToken: " || $response("nextPageToken")
  ]
}

return $get_messages()
```

There are a few things you can configure, including the number of messages to retrieve, the query (set to `is:unread` here), and the page token (my code prints it out, but I didn't bother to implement pagination, which is pretty easy). If the userId `me` doesn't work for you, you can also try to replace it with your actual email address.

The moment of truth:

```console
$ perl saxon-lint.pl --xpath "$(<gmail.xpath)" - | python3 -c 'import sys, html; sys.stdout.write(html.unescape(sys.stdin.read()))'
```

The Python part performs an unescape of XML character/entity references. That's not a limitation of XPath, but rather, saxon-lint, which, as an XML tool, refuses to print what we ask it to print without escaping first.

Here's a showcase of the output, with some (heavily redacted) unread emails from my inbox:

- Some text/plain LKML patch.
- Another LKML patch, with a gzip attachment.
- A multipart/alternative invoice from Linode, with the text/html part ommitted, since it's long and unreadable.
- Another multipart/alternative, this time from YouTube notifying me that a three-year-old video of mine has been blocked in some countries due to some copyrighted track. Thanks YouTube!
- A text/html from Docker annoucing rate limits.

An aside on text/html: I tried to decode them with [`parse-xml`](https://www.w3.org/TR/xpath-functions-31/#func-parse-xml) to extract the text, unfortunately people have problems writing/generating valid XML even when they declare XHTML in doctype, so that was a failure. So here's a proposal for W3C XPath version 3.2/4.0: `fn:parse-html`. Maybe embed a JavaScript engine too!

```
********************************************************************************
Gmail Message-ID: <redacted>
Message-ID:
Subject: [PATCH] nfsd: remove unneeded semicolon
From: <redacted>
To: <redacted>
Date: Sun,  1 Nov 2020 07:32:34 -0800
------------------------------------- Body -------------------------------------
From: Tom Rix <redacted>

A semicolon is not needed after a switch statement.

Signed-off-by: Tom Rix <redacted>
---
fs/nfsd/nfs4xdr.c | 2 +-
1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/fs/nfsd/nfs4xdr.c b/fs/nfsd/nfs4xdr.c
index 259d5ad0e3f4..6020f0ff6795 100644
--- a/fs/nfsd/nfs4xdr.c
+++ b/fs/nfsd/nfs4xdr.c
@@ -2558,7 +2558,7 @@ static u32 nfs4_file_type(umode_t mode)
case S_IFREG:   return NF4REG;
case S_IFSOCK:  return NF4SOCK;
default:        return NF4BAD;
-       };
+       }
}

static inline __be32
--
2.18.1

********************************************************************************
Gmail Message-ID: <redacted>
Message-ID: <redacted>
Subject: Re: [PATCH v5] driver/perf: Add PMU driver for the ARM DMC-620 memory controller
From: kernel test robot <lkp@intel.com>
To: Tuan Phan <tuanphan@os.amperecomputing.com>
Date: Sun, 1 Nov 2020 21:58:05 +0800
------------------------------ Part (text/plain) -------------------------------
Hi Tuan,

Thank you for the patch! Yet something to improve:

[auto build test ERROR on linus/master]
[also build test ERROR on v5.10-rc1 next-20201030]
[If your patch is applied to the wrong git tree, kindly drop us a note.
And when submitting patch, we suggest to use '--base' as documented in
https://git-scm.com/docs/git-format-patch]

url:    https://github.com/0day-ci/linux/commits/Tuan-Phan/driver-perf-Add-PMU-driver-for-the-ARM-DMC-620-memory-controller/20201030-053103
base:   https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git b9c0f4bd5b8114ee1773734e07cda921b6e8248b
config: s390-allmodconfig (attached as .config)
compiler: s390-linux-gcc (GCC) 9.3.0
reproduce (this is a W=1 build):
wget https://raw.githubusercontent.com/intel/lkp-tests/master/sbin/make.cross -O ~/bin/make.cross
chmod +x ~/bin/make.cross
# https://github.com/0day-ci/linux/commit/62ac0a881cd6542a712a719313ada898e19afbaf
git remote add linux-review https://github.com/0day-ci/linux
git fetch --no-tags linux-review Tuan-Phan/driver-perf-Add-PMU-driver-for-the-ARM-DMC-620-memory-controller/20201030-053103
git checkout 62ac0a881cd6542a712a719313ada898e19afbaf
# save the attached .config to linux build tree
COMPILER_INSTALL_PATH=$HOME/0day COMPILER=gcc-9.3.0 make.cross ARCH=s390

If you fix the issue, kindly add following tag as appropriate
Reported-by: kernel test robot <lkp@intel.com>

All errors (new ones prefixed by >>):

In file included from drivers/perf/arm_dmc620_pmu.c:26:
>> include/linux/perf/arm_pmu.h:15:10: fatal error: asm/cputype.h: No such file or directory
15 | #include <asm/cputype.h>
|          ^~~~~~~~~~~~~~~
compilation terminated.

vim +15 include/linux/perf/arm_pmu.h

0f4f0672ac950c arch/arm/include/asm/pmu.h   Jamie Iles    2010-02-02  10
0e25a5c9806728 arch/arm/include/asm/pmu.h   Rabin Vincent 2011-02-08  11  #include <linux/interrupt.h>
0ce47080dfffe7 arch/arm/include/asm/pmu.h   Mark Rutland  2011-05-19  12  #include <linux/perf_event.h>
167e61438da066 include/linux/perf/arm_pmu.h Mark Rutland  2017-10-09  13  #include <linux/platform_device.h>
86cdd72af93686 include/linux/perf/arm_pmu.h Mark Rutland  2016-09-09  14  #include <linux/sysfs.h>
548a86cae48584 arch/arm/include/asm/pmu.h   Mark Rutland  2014-05-23 @15  #include <asm/cputype.h>
548a86cae48584 arch/arm/include/asm/pmu.h   Mark Rutland  2014-05-23  16

---
0-DAY CI Kernel Test Service, Intel Corporation
https://lists.01.org/hyperkitty/list/kbuild-all@lists.01.org
--------------------------- Part (application/gzip) ----------------------------
Attachment (64299 bytes) omitted
********************************************************************************
Gmail Message-ID: <redacted>
Message-ID: <redacted>
Subject: Linode - Invoice [<redacted>]
From: billing@linode.com
To: <redacted>
Date: <redacted>
------------------------------ Part (text/plain) -------------------------------
Invoice Number: <redacted>
Invoice Date: <redacted>
Invoice To: <redacted>

<a lot of redacted>

Thank you,
The Linode Team
http://www.linode.com/
------------------------------- Part (text/html) -------------------------------
HTML (<redacted> bytes) omitted
********************************************************************************
Gmail Message-ID: <redacted>
Message-ID: <redacted>
Subject: [Copyright claim] Your video has been blocked in some countries: <redacted>
From: YouTube <accounts-noreply@youtube.com>
To: <redacted>
Date: <redacted>
------------------------------ Part (text/plain) -------------------------------
Hi <redacted>,

A copyright owner using Content ID has claimed some material in your video.

As a result, your video has been blocked in some countries. This means that
your video is still up on YouTube, but people in some countries may not be
able to watch it.

This is not a copyright strike. This claim does not affect your account
status.

Video title: <redacted>
Copyrighted content: <redacted>
Claimed by: <redacted>


Why this can happen
Your video might contain copyrighted content.
Copyright owners can choose to block YouTube videos that contain their
content.

If this copyright claim is valid
You don't need to take any action or delete your video.

How to unblock your video
If something went wrong and the copyright owner or our system made a
mistake, we have a dispute process. Please only use it if you're confident
you have the rights to use all the content in your video.
You can also remove the claimed content using Studio's editing tools.

View options: <redacted>

- The YouTube Team

------------------------------- Part (text/html) -------------------------------
HTML (<redacted> bytes) omitted
********************************************************************************
Gmail Message-ID: <redacted>
Message-ID:
Subject: Service Announcement: Pull Rate Limit Enforcement, Changes to Image Retention Policies Begin November 2, 2020
From: Docker <noreply@notify.docker.com>
To: <redacted>
Date: <redacted>
------------------------------------- Body -------------------------------------

<!DOCTYPE html>
<html lang="en">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
<style>
a {
text-decoration: none !important;
}
</style>
</head>
<body style="margin: 0 auto; font-family: 'Open Sans', sans-serif; color: #26323f;  max-width: 520px; padding: 0 20px;">
<div style="padding-top: 75px; text-align: center;">
<a style="color: #0073ec;" target="_blank" rel="noopener noreferrer" href="<redacted>">
<img alt="Docker" width="105" height="27" src="https://d36jcksde1wxzq.cloudfront.net/saas-mega/DockerWhaleIcon.png"/>
</a>
</div>
<div style="color:#828282; margin-bottom: 50px; font-size: 13px;">
<p>
Hello:
</p>
<p>
You are receiving this email because of a policy change to Docker products and services you use. On Monday, November 2, 2020 at 9am Pacific Standard Time, Docker will begin enforcing rate limits on container pulls for Anonymous and Free users. Anonymous (unauthenticated) users will be limited to 100 container image pulls every six hours, and Free (authenticated) users will be limited to 200 container image pulls every six hours, when enforcement is fully implemented. Docker Pro and Team subscribers can pull container images from Docker Hub without restriction, as long as the quantities are not excessive or abusive.
</p>
<p>
In addition, we are pausing enforcement of the changes to our image-retention policies until mid-2021, when we anticipate incorporating them into usage-based pricing. Two months ago, we announced an update to Docker image-retention policies. As originally stated, this change, which was set to take effect on November 1, 2020, would result in the deletion of images for free Docker account users after six months of inactivity. Todayâ€™s announcement means Docker will not enforce image expiration on November 1, 2020.
</p>
<p>
For more details, please <a href="<redacted>">read the blog post</a> summarizing the changes or <a href="<redacted>">review the documentation for rate limits</a>.
</p>
<p>
Details about Docker subscription levels and differentiators are available on the <a href="<redacted>">Docker Pricing Page</a>.
</p>
<p>
Thank you for using Docker.
</p>
<p>
Jean-Laurent de Morlhon <br>
VP, Engineering <br>
Docker
</p>
</div>
<div style="font-family: Helvetica, sans-serif; vertical-align: top; padding: 20px 11px; font-size: 12px; color: #000000; text-align: center; background: #fff" valign="top">
Â© Docker, Inc., 2020 <br>
318 Cambridge Ave <br>
Palo Alto, CA 94306 <br><br>
<a href="<redacted>"> Docker Privacy Policy </a>
</div>
<img width="1px" height="1px" alt="" src="<redacted>"></body>
</html>

********************************************************************************
nextPageToken: <redacted>
```

## Further reading

- https://news.ycombinator.com/item?id=24941663
- https://tomforb.es/xcat-1.0-released-or-xpath-injection-issues-are-severely-underrated/
- https://github.com/whatwg/dom/issues/903
- https://news.ycombinator.com/item?id=24765868

## License

Included Saxon-HE 10.3 and saxon-lint.pl (both included for convenience) are licensed under [Mozilla Public License (MPL) 2.0](https://mozilla.org/MPL/2.0/).

Yours truly's code, which is NOT derivative of the above, is licensed under WTFPL.
