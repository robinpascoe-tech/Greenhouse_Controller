<?php
// MySQL Database Connect
include 'dbconnect.php';

// Timezones
$user_tz = new DateTimeZone('America/Toronto');
$utc_tz  = new DateTimeZone('UTC');

// Get form values
$windowoverridetime = isset($_POST['windowoverridetime']) ? trim($_POST['windowoverridetime']) : '';
$windowstatus       = isset($_POST['windowstatus']) ? (int) $_POST['windowstatus'] : 0;

$fanoverridetime    = isset($_POST['fanoverridetime']) ? trim($_POST['fanoverridetime']) : '';
$fanstatus          = isset($_POST['fanstatus']) ? (int) $_POST['fanstatus'] : 0;

$isformerror = 0;
$formerror = "";

if ($windowstatus == -1) {
    $windowstatusname = 'Closed';
} elseif ($windowstatus == 1) {
    $windowstatusname = 'Open';
} else {
    $windowstatusname = 'Automatic';
}

if ($fanstatus == -1) {
    $fanstatusname = 'Off';
} elseif ($fanstatus == 1) {
    $fanstatusname = 'On';
} else {
    $fanstatusname = 'Automatic';
}

// Variables used later for confirmation display
$window_expire_local = null;
$fan_expire_local = null;

// Process window override
if ($windowoverridetime === '') {
    $formerror .= "No Window Change";
    $isformerror = 1;
} else {
    $windowoverridetime = (int) $windowoverridetime;

    if ($windowoverridetime <= 0) {
        $formerror .= "Invalid Window Override Time";
        $isformerror = 1;
    } else {
        // Current local Toronto time
        $window_expire_local = new DateTime('now', $user_tz);

        // Add requested number of minutes
        $window_expire_local->add(new DateInterval("PT{$windowoverridetime}M"));

        // Clone and convert to UTC for database storage
        $window_expire_utc = clone $window_expire_local;
        $window_expire_utc->setTimeZone($utc_tz);

        $newwindow_time = $window_expire_utc->format('Y-m-d H:i:s');

        $data = "UPDATE `overrides`
                 SET windowoverride='$windowstatus',
                     windowexpire='$newwindow_time'
                 WHERE ID='1'";

        $query = mysqli_query($connection, $data)
            or die("Couldn't execute query. " . mysqli_error($connection));
    }
}

// Process fan override
if ($fanoverridetime === '') {
    if ($formerror !== "") {
        $formerror .= "<br>";
    }

    $formerror .= "No Fan Change";
    $isformerror = 1;
} else {
    $fanoverridetime = (int) $fanoverridetime;

    if ($fanoverridetime <= 0) {
        if ($formerror !== "") {
            $formerror .= "<br>";
        }

        $formerror .= "Invalid Fan Override Time";
        $isformerror = 1;
    } else {
        // Current local Toronto time
        $fan_expire_local = new DateTime('now', $user_tz);

        // Add requested number of minutes
        $fan_expire_local->add(new DateInterval("PT{$fanoverridetime}M"));

        // Clone and convert to UTC for database storage
        $fan_expire_utc = clone $fan_expire_local;
        $fan_expire_utc->setTimeZone($utc_tz);

        $newfan_time = $fan_expire_utc->format('Y-m-d H:i:s');

        $data = "UPDATE `overrides`
                 SET fanoverride='$fanstatus',
                     fanexpire='$newfan_time'
                 WHERE ID='1'";

        $query = mysqli_query($connection, $data)
            or die("Couldn't execute query. " . mysqli_error($connection));
    }
}
?>

<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"
"http://www.w3.org/TR/html4/loose.dtd">

<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Greenhouse Settings Confirmation</title>

    <style type="text/css">
    .error-style {
        color: #FA0000;
        font-size: x-large;
    }

    .wrap {
        width: 300px;
        margin: 0 auto;
        background-color: #ffffff;
        opacity: 0.9;
        border-radius: 25px;
        text-align: center;
    }

    body {
        background-image: url("/images/greenhousebg4.jpg");
        background-repeat: no-repeat;
        background-position: center top;
        background-attachment: fixed;
    }
    </style>
</head>

<body>
<div class="wrap">
<br>

<?php
if ($isformerror == 1) {
    echo '<p class="error-style"><strong>' . $formerror . '</strong><br></p>';
}
?>

<?php
if ($window_expire_local !== null) {
    echo 'Window will remain <strong>' . $windowstatusname . '</strong> for <strong>' .
         $windowoverridetime . '</strong> minute';

    if ($windowoverridetime != 1) {
        echo 's';
    }

    echo ' until <strong>' . $window_expire_local->format('D M d g:i a') . '</strong>';
}
?>

<br>

<?php
if ($fan_expire_local !== null) {
    echo 'Fan will remain <strong>' . $fanstatusname . '</strong> for <strong>' .
         $fanoverridetime . '</strong> minute';

    if ($fanoverridetime != 1) {
        echo 's';
    }

    echo ' until <strong>' . $fan_expire_local->format('D M d g:i a') . '</strong>';
}
?>

<br>

<p><a href="overrideform.php">Back to Settings</a></p>
<p><a href="index.php">Home</a></p>
<br>

</div>
</body>
</html>

