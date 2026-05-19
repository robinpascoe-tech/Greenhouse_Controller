<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">
<html>
<?php
  $bg = array('greenhousebg4.jpg', 'greenhousebg5.jpg', 'greenhousebg6.jpg', 'greenhousebg7.jpg', 'greenhousebg8.jpg', 'greenhousebg9.jpg', 'greenhousebg10.jpg', 'greenhousebg11.jpg', 'greenhousebg12.jpg', 'greenhousebg13.jpg' ); // array of filenames

  $i = rand(0, count($bg)-1); // generate random number size of the array
  $selectedBg = "$bg[$i]"; // set variable equal to which random filename was chosen
?>
<head>
<meta content="en-ca" http-equiv="Content-Language">
<meta content="text/html; charset=utf-8" http-equiv="Content-Type">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Greenhouse Temperatures</title>
<link rel="shortcut icon" type="image/x-icon" href="images/greenhouseicon.ico">
<style type="text/css">
<!--
body{
background: url(images/<?php echo $selectedBg; ?>) no-repeat;
}
-->
</style>
<link rel='stylesheet' type='text/css' href='css/style.css' />
<link id="size-stylesheet" rel='stylesheet' type='text/css' href='css/narrow.css' />
<script type="text/javascript" src="/jquery/jquery.min.js"></script>
<script type='text/javascript' src='js/resolution-test.js'></script>
<script src="../amcharts2/amcharts.js" type="text/javascript"></script>
<script src="../amcharts2/gauge.js" type="text/javascript"></script>
<script>
			var chartfronttemp;
			var arrowfronttemp;
			var axisfronttempC;
			var axisfronttempF;

			var chartbacktemp;
			var arrowbacktemp;
			var axisbacktempC;
			var axisbacktempF;

			var chartavgtemp;
			var arrowavgtemp;
			var axisavgtempC;
			var axisavgtempF;

			var chartoutsidetemp;
			var arrowoutsidetemp;
			var axisoutsidetempC;
			var axisoutsidetempF;			

			var chartwoodstovetemp;
			var arrowwoodstovetemp;
			var axiswoodstovetempC;
			var axiswoodstovetempF;	
			
			AmCharts.ready(function () {

				// create angular gauge
				chartfronttemp = new AmCharts.AmAngularGauge();
				chartfronttemp.radius = "45%";
				chartfronttemp.addTitle("Front Temperature");
				chartfronttemp.panEventsEnabled = false;


				// kilometers axis
				axisfronttempC = new AmCharts.GaugeAxis();
				axisfronttempC.startValue = 0;
				axisfronttempC.endValue = 50;
				axisfronttempC.radius = "100%";
				axisfronttempC.inside = false;
				axisfronttempC.gridInside = false;
				axisfronttempC.axisColor = "#94dca0";
				axisfronttempC.tickColor = "#94dca0";
				axisfronttempC.axisThickness = 1;
				axisfronttempC.valueInterval = 5;
				// bottom text
                axisfronttempC.bottomTextYOffset = -25;
				chartfronttemp.addAxis(axisfronttempC);
				
                // color bands
                var band1 = new AmCharts.GaugeBand();
                band1.startValue = 12;
                band1.endValue = 35;
                band1.color = "#00CC00";

                var band2 = new AmCharts.GaugeBand();
                band2.startValue = 8;
                band2.endValue = 12;
                band2.color = "#ffac29";

                var band3 = new AmCharts.GaugeBand();
                band3.startValue = 0;
                band3.endValue = 8;
                band3.color = "#ea3838";
				
				var band4 = new AmCharts.GaugeBand();
                band4.startValue = 35;
                band4.endValue = 40;
                band4.color = "#ffac29";
				
				var band5 = new AmCharts.GaugeBand();
                band5.startValue = 40;
                band5.endValue = 50;
                band5.color = "#ea3838";
                
                axisfronttempC.bands = [band1, band2, band3, band4, band5];

				// miles axis
				axisfronttempF = new AmCharts.GaugeAxis();
				axisfronttempF.startValue = 32;
				axisfronttempF.endValue = 122;
				axisfronttempF.radius = "80%";
				axisfronttempF.axisColor = "#bebd61";
				axisfronttempF.tickColor = "#bebd61";
				axisfronttempF.axisThickness = 1;
				axisfronttempF.valueInterval = 9;
				// bottom text
                axisfronttempF.bottomTextYOffset = -30;
				chartfronttemp.addAxis(axisfronttempF);

				// arrow
				arrowfronttemp = new AmCharts.GaugeArrow();
				arrowfronttemp.radius = "85%";
				arrowfronttemp.color = "#8ec487";
				arrowfronttemp.innerRadius = 20;
				arrowfronttemp.nailRadius = 0;
				chartfronttemp.addArrow(arrowfronttemp);

	//second Chart
				// create angular gauge
				chartbacktemp = new AmCharts.AmAngularGauge();
				chartbacktemp.radius = "45%";
				chartbacktemp.addTitle("Back Temperature");
				chartbacktemp.panEventsEnabled = false;

				// kilometers axis
				axisbacktempC = new AmCharts.GaugeAxis();
				axisbacktempC.startValue = 0;
				axisbacktempC.endValue = 50;
				axisbacktempC.radius = "100%";
				axisbacktempC.inside = false;
				axisbacktempC.gridInside = false;
				axisbacktempC.axisColor = "#94dca0";
				axisbacktempC.tickColor = "#94dca0";
				axisbacktempC.axisThickness = 1;
				axisbacktempC.valueInterval = 5;
				// bottom text
                axisbacktempC.bottomTextYOffset = -25;
				chartbacktemp.addAxis(axisbacktempC);
				
                // color bands

                
                axisbacktempC.bands = [band1, band2, band3, band4, band5];

				// miles axis
				axisbacktempF = new AmCharts.GaugeAxis();
				axisbacktempF.startValue = 32;
				axisbacktempF.endValue = 122;
				axisbacktempF.radius = "80%";
				axisbacktempF.axisColor = "#bebd61";
				axisbacktempF.tickColor = "#bebd61";
				axisbacktempF.axisThickness = 1;
				axisbacktempF.valueInterval = 9;
				// bottom text
                axisbacktempF.bottomTextYOffset = -30;
				chartbacktemp.addAxis(axisbacktempF);

				// arrow
				arrowbacktemp = new AmCharts.GaugeArrow();
				arrowbacktemp.radius = "85%";
				arrowbacktemp.color = "#8ec487";
				arrowbacktemp.innerRadius = 20;
				arrowbacktemp.nailRadius = 0;
				chartbacktemp.addArrow(arrowbacktemp);
				
	//average temp Chart
				// create angular gauge
				chartavgtemp = new AmCharts.AmAngularGauge();
				chartavgtemp.radius = "45%";
				chartavgtemp.addTitle("Avg Inside Temperature");
				chartavgtemp.panEventsEnabled = false;

				// kilometers axis
				axisavgtempC = new AmCharts.GaugeAxis();
				axisavgtempC.startValue = 0;
				axisavgtempC.endValue = 50;
				axisavgtempC.radius = "100%";
				axisavgtempC.inside = false;
				axisavgtempC.gridInside = false;
				axisavgtempC.axisColor = "#94dca0";
				axisavgtempC.tickColor = "#94dca0";
				axisavgtempC.axisThickness = 1;
				axisavgtempC.valueInterval = 5;
				// bottom text
                axisavgtempC.bottomTextYOffset = -25;
				chartavgtemp.addAxis(axisavgtempC);
				
                // color bands

                
                axisavgtempC.bands = [band1, band2, band3, band4, band5];

				// miles axis
				axisavgtempF = new AmCharts.GaugeAxis();
				axisavgtempF.startValue = 32;
				axisavgtempF.endValue = 122;
				axisavgtempF.radius = "80%";
				axisavgtempF.axisColor = "#bebd61";
				axisavgtempF.tickColor = "#bebd61";
				axisavgtempF.axisThickness = 1;
				axisavgtempF.valueInterval = 9;
				// bottom text
                axisavgtempF.bottomTextYOffset = -30;
				chartavgtemp.addAxis(axisavgtempF);

				// arrow
				arrowavgtemp = new AmCharts.GaugeArrow();
				arrowavgtemp.radius = "85%";
				arrowavgtemp.color = "#8ec487";
				arrowavgtemp.innerRadius = 20;
				arrowavgtemp.nailRadius = 0;
				chartavgtemp.addArrow(arrowavgtemp);

	//Outside Temp Chart
				// create angular gauge
				chartoutsidetemp = new AmCharts.AmAngularGauge();
				chartoutsidetemp.radius = "45%";
				chartoutsidetemp.addTitle("Outside Temperature");
				chartoutsidetemp.panEventsEnabled = false;

				// kilometers axis
				axisoutsidetempC = new AmCharts.GaugeAxis();
				axisoutsidetempC.startValue = -5;
				axisoutsidetempC.endValue = 45;
				axisoutsidetempC.radius = "100%";
				axisoutsidetempC.inside = false;
				axisoutsidetempC.gridInside = false;
				axisoutsidetempC.axisColor = "#94dca0";
				axisoutsidetempC.tickColor = "#94dca0";
				axisoutsidetempC.axisThickness = 1;
				axisoutsidetempC.valueInterval = 5;
				// bottom text
                axisoutsidetempC.bottomTextYOffset = -25;
				chartoutsidetemp.addAxis(axisoutsidetempC);
				
                // color bands
                var band1outside = new AmCharts.GaugeBand();
                band1outside.startValue = 12;
                band1outside.endValue = 35;
                band1outside.color = "#00CC00";

                var band2outside = new AmCharts.GaugeBand();
                band2outside.startValue = 8;
                band2outside.endValue = 12;
                band2outside.color = "#ffac29";

                var band3outside = new AmCharts.GaugeBand();
                band3outside.startValue = 0;
                band3outside.endValue = 8;
                band3outside.color = "#ea3838";
				
				var band4outside = new AmCharts.GaugeBand();
                band4outside.startValue = 35;
                band4outside.endValue = 40;
                band4outside.color = "#ffac29";
				
				var band5outside = new AmCharts.GaugeBand();
                band5outside.startValue = 40;
                band5outside.endValue = 45;
                band5outside.color = "#ea3838";

				var band6outside = new AmCharts.GaugeBand();
                band6outside.startValue = -5;
                band6outside.endValue = 0;
                band6outside.color = "#0000cc";
                
                axisoutsidetempC.bands = [band1outside, band2outside, band3outside, band4outside, band5outside, band6outside];

				// miles axis
				axisoutsidetempF = new AmCharts.GaugeAxis();
				axisoutsidetempF.startValue = 23;
				axisoutsidetempF.endValue = 113;
				axisoutsidetempF.radius = "80%";
				axisoutsidetempF.axisColor = "#bebd61";
				axisoutsidetempF.tickColor = "#bebd61";
				axisoutsidetempF.axisThickness = 1;
				axisoutsidetempF.valueInterval = 9;
				// bottom text
                axisoutsidetempF.bottomTextYOffset = -30;
				chartoutsidetemp.addAxis(axisoutsidetempF);

				// arrow
				arrowoutsidetemp = new AmCharts.GaugeArrow();
				arrowoutsidetemp.radius = "85%";
				arrowoutsidetemp.color = "#8ec487";
				arrowoutsidetemp.innerRadius = 20;
				arrowoutsidetemp.nailRadius = 0;
				chartoutsidetemp.addArrow(arrowoutsidetemp);

//woodstove Temp Chart
				// create angular gauge
				chartwoodstovetemp = new AmCharts.AmAngularGauge();
				chartwoodstovetemp.radius = "45%";
				chartwoodstovetemp.addTitle("Woodstove Temperature");
				chartwoodstovetemp.panEventsEnabled = false;

				// kilometers axis
				axiswoodstovetempC = new AmCharts.GaugeAxis();
				axiswoodstovetempC.startValue = 15;
				axiswoodstovetempC.endValue = 80;
				axiswoodstovetempC.radius = "100%";
				axiswoodstovetempC.inside = false;
				axiswoodstovetempC.gridInside = false;
				axiswoodstovetempC.axisColor = "#94dca0";
				axiswoodstovetempC.tickColor = "#94dca0";
				axiswoodstovetempC.axisThickness = 1;
				axiswoodstovetempC.valueInterval = 5;
				// bottom text
                axiswoodstovetempC.bottomTextYOffset = -25;
				chartwoodstovetemp.addAxis(axiswoodstovetempC);
				
                // color bands
                var band1woodstove = new AmCharts.GaugeBand();
                band1woodstove.startValue = 15;
                band1woodstove.endValue = 20;
                band1woodstove.color = "#00CC00";

                var band2woodstove = new AmCharts.GaugeBand();
                band2woodstove.startValue = 20;
                band2woodstove.endValue = 30;
                band2woodstove.color = "#ffac29";

                var band3woodstove = new AmCharts.GaugeBand();
                band3woodstove.startValue = 30;
                band3woodstove.endValue = 80;
                band3woodstove.color = "#ea3838";
				
				axiswoodstovetempC.bands = [band1woodstove, band2woodstove, band3woodstove];

				// miles axis
				axiswoodstovetempF = new AmCharts.GaugeAxis();
				axiswoodstovetempF.startValue = 59;
				axiswoodstovetempF.endValue = 176;
				axiswoodstovetempF.radius = "80%";
				axiswoodstovetempF.axisColor = "#bebd61";
				axiswoodstovetempF.tickColor = "#bebd61";
				axiswoodstovetempF.axisThickness = 1;
				axiswoodstovetempF.valueInterval = 9;
				// bottom text
                axiswoodstovetempF.bottomTextYOffset = -30;
				chartwoodstovetemp.addAxis(axiswoodstovetempF);

				// arrow
				arrowwoodstovetemp = new AmCharts.GaugeArrow();
				arrowwoodstovetemp.radius = "85%";
				arrowwoodstovetemp.color = "#8ec487";
				arrowwoodstovetemp.innerRadius = 20;
				arrowwoodstovetemp.nailRadius = 0;
				chartwoodstovetemp.addArrow(arrowwoodstovetemp);
				
//write charts				

				chartfronttemp.write("chartfronttempdiv");
				chartbacktemp.write("chartbacktempdiv");
				chartavgtemp.write("chartavgtempdiv");
				chartoutsidetemp.write("chartoutsidetempdiv");
				chartwoodstovetemp.write("chartwoodstovetempdiv");
                // change value every 5 seconds
                setInterval(updateTemps, 5000);
   
				
			});
			
			
            // set random value
            function updateTemps() {
				var data = {
				"action": "test"
				};
				data = $(this).serialize() + "&" + $.param(data);
				$.ajax({
				type: "POST",
				dataType: "json",
				url: "gettempsall.php", //Relative or absolute path to response.php file
				data: data,
				success: function(data) {
					arrowbacktemp.setValue(data[0]);
					axisbacktempC.setBottomText(data[0] + " \xB0C");
					axisbacktempF.setBottomText(data[1] + " \xB0F");
					arrowfronttemp.setValue(data[2]);
					axisfronttempC.setBottomText(data[2] + " \xB0C");
					axisfronttempF.setBottomText(data[3] + " \xB0F");
					arrowavgtemp.setValue(data[6]);
					axisavgtempC.setBottomText(data[6] + " \xB0C");
					axisavgtempF.setBottomText(data[7] + " \xB0F");
					arrowoutsidetemp.setValue(data[4]);
					axisoutsidetempC.setBottomText(data[4] + " \xB0C");
					axisoutsidetempF.setBottomText(data[5] + " \xB0F");
					arrowwoodstovetemp.setValue(data[8]);
					axiswoodstovetempC.setBottomText(data[8] + " \xB0C");
					axiswoodstovetempF.setBottomText(data[9] + " \xB0F");
      			}
				});
			}
			
        </script>
</head>
<body>
<div id="pagewrap">
<div id="floatcontainer">
<div class="gauges" id="chartfronttempdiv"></div>
<div class="gauges" id="chartbacktempdiv"></div>
</div>
<div id="floatcontainer">
<div class="gauges" id="chartavgtempdiv"></div>
<div class="gauges" id="chartoutsidetempdiv"></div>
</div>
<div class="gauges" id="chartwoodstovetempdiv"></div>
<div class="wrap" id="moreinfo">
<table style="width: 300px" align="center">
	<tr>
		<td class="auto-style9" style="width: 199px"><br><a href="index.php"><img alt="Thermometer" height="100" src="images/greenhousehome.png" width="100"><br>Home</a><br><br></td>
	</tr>
</table>
</div>
</div>
</body>
</html>