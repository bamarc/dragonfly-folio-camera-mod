// SPDX-License-Identifier: GPL-2.0-only
/*
 * Texas Instruments LM3643 Dual Flash LED Driver
 * ACPI ID: TXNW3643
 *
 * Exposes /sys/class/leds/lm3643:torch for IR facial illumination.
 */

#include <linux/delay.h>
#include <linux/gpio/consumer.h>
#include <linux/i2c.h>
#include <linux/leds.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/regmap.h>
#include <linux/slab.h>
#include <linux/acpi.h>
#include <linux/pm_runtime.h>

#define LM3643_NAME		"leds-lm3643"

/* Register Definitions */
#define LM3643_REG_ENABLE	0x01
#define LM3643_REG_FLASH_BRT	0x02
#define LM3643_REG_TORCH_BRT	0x03
#define LM3643_REG_FLASH_TOUT	0x04
#define LM3643_REG_FLAGS	0x05
#define LM3643_REG_DEV_ID	0x06
#define LM3643_REG_BOOST	0x07

/* Mode bits in REG_ENABLE [3:2] */
#define LM3643_MODE_STANDBY	(0x00 << 2)
#define LM3643_MODE_INDICATOR	(0x01 << 2)
#define LM3643_MODE_TORCH	(0x02 << 2)
#define LM3643_MODE_FLASH	(0x03 << 2)

/* LED Enable bits in REG_ENABLE [1:0] */
#define LM3643_LED1_EN		BIT(0)
#define LM3643_LED2_EN		BIT(1)
#define LM3643_LEDS_BOTH	(LM3643_LED1_EN | LM3643_LED2_EN)

/* Pin control bits in REG_ENABLE [7:4] */
#define LM3643_TX_PIN_EN	BIT(7)
#define LM3643_STROBE_TYPE	BIT(6)
#define LM3643_STROBE_EN	BIT(5)
#define LM3643_TORCH_TEMP_EN	BIT(4)

struct lm3643_chip {
	struct device *dev;
	struct i2c_client *client;
	struct regmap *regmap;
	struct gpio_desc *enable_gpio;
	struct mutex lock;

	struct led_classdev cdev_torch;
	u8 torch_brightness;
};

static const struct regmap_config lm3643_regmap_config = {
	.reg_bits = 8,
	.val_bits = 8,
	.max_register = 0x08,
	.cache_type = REGCACHE_NONE,
};

static int lm3643_torch_set(struct led_classdev *cdev,
			    enum led_brightness brightness)
{
	struct lm3643_chip *chip = container_of(cdev, struct lm3643_chip, cdev_torch);
	struct device *host_dev = chip->client->adapter->dev.parent;
	int ret = 0;

	if (host_dev) {
		ret = pm_runtime_get_sync(host_dev);
		if (ret < 0) {
			pm_runtime_put_noidle(host_dev);
			dev_err(chip->dev, "Failed to wake I2C host: %d\n", ret);
			return ret;
		}
	}

	mutex_lock(&chip->lock);

	if (brightness == LED_OFF) {
		/* Return to standby: Mode = 00, LEDs disabled */
		ret = regmap_write(chip->regmap, LM3643_REG_ENABLE, LM3643_MODE_STANDBY);
		if (ret)
			dev_err(chip->dev, "Failed to disable torch: %d\n", ret);
		chip->torch_brightness = 0;
	} else {
		/* Ensure HW enable GPIO is asserted */
		if (chip->enable_gpio)
			gpiod_set_value_cansleep(chip->enable_gpio, 1);

		/* Scale brightness (1-255 maps to 0-127 current code) */
		u8 brt_code = (brightness > 127) ? 127 : (u8)brightness;
		if (brt_code == 0 && brightness > 0)
			brt_code = 1;

		ret = regmap_write(chip->regmap, LM3643_REG_TORCH_BRT, brt_code);
		if (ret) {
			dev_err(chip->dev, "Failed to set torch brightness: %d\n", ret);
			goto out;
		}

		/* Enable torch: Mode = 10, LED1 + LED2 enabled, disable TX/Torch pin traps */
		u8 enable_val = LM3643_MODE_TORCH | LM3643_LEDS_BOTH;
		ret = regmap_write(chip->regmap, LM3643_REG_ENABLE, enable_val);
		if (ret) {
			dev_err(chip->dev, "Failed to enable torch mode: %d\n", ret);
			goto out;
		}

		chip->torch_brightness = brt_code;
	}

out:
	mutex_unlock(&chip->lock);

	if (host_dev)
		pm_runtime_put(host_dev);

	return ret;
}

static int lm3643_probe(struct i2c_client *client)
{
	struct device *dev = &client->dev;
	struct device *host_dev = client->adapter->dev.parent;
	struct lm3643_chip *chip;
	unsigned int dev_id = 0;
	int ret;

	chip = devm_kzalloc(dev, sizeof(*chip), GFP_KERNEL);
	if (!chip)
		return -ENOMEM;

	chip->dev = dev;
	chip->client = client;
	mutex_init(&chip->lock);
	i2c_set_clientdata(client, chip);

	/* Get optional HW enable GPIO from ACPI _CRS */
	chip->enable_gpio = devm_gpiod_get_optional(dev, NULL, GPIOD_OUT_HIGH);
	if (IS_ERR(chip->enable_gpio)) {
		dev_warn(dev, "Failed to get enable GPIO: %ld\n", PTR_ERR(chip->enable_gpio));
		chip->enable_gpio = NULL;
	} else if (chip->enable_gpio) {
		gpiod_set_value_cansleep(chip->enable_gpio, 1);
		msleep(5);
		dev_info(dev, "Asserted hardware enable GPIO\n");
	}

	chip->regmap = devm_regmap_init_i2c(client, &lm3643_regmap_config);
	if (IS_ERR(chip->regmap)) {
		ret = PTR_ERR(chip->regmap);
		dev_err(dev, "Failed to allocate regmap: %d\n", ret);
		return ret;
	}

	/* Wake parent I2C host adapter before probe communication */
	if (host_dev)
		pm_runtime_get_sync(host_dev);

	/* Verify communication by reading Device ID register */
	ret = regmap_read(chip->regmap, LM3643_REG_DEV_ID, &dev_id);
	if (ret) {
		dev_err(dev, "Failed to read Device ID register (ret=%d)\n", ret);
		/* If unpowered, do not abort probe; allow runtime activation */
	} else {
		dev_info(dev, "LM3643 Device ID: 0x%02x\n", dev_id);
	}

	/* Initialize to Standby Mode */
	regmap_write(chip->regmap, LM3643_REG_ENABLE, LM3643_MODE_STANDBY);

	if (host_dev)
		pm_runtime_put(host_dev);

	/* Register torch LED class device */
	chip->cdev_torch.name = "lm3643:torch";
	chip->cdev_torch.max_brightness = 127;
	chip->cdev_torch.brightness_set_blocking = lm3643_torch_set;
	chip->cdev_torch.flags = LED_CORE_SUSPENDRESUME;

	ret = devm_led_classdev_register(dev, &chip->cdev_torch);
	if (ret) {
		dev_err(dev, "Failed to register torch LED class: %d\n", ret);
		return ret;
	}

	dev_info(dev, "LM3643 IR Flash driver successfully registered (/sys/class/leds/lm3643:torch)\n");
	return 0;
}

static void lm3643_remove(struct i2c_client *client)
{
	struct lm3643_chip *chip = i2c_get_clientdata(client);

	regmap_write(chip->regmap, LM3643_REG_ENABLE, LM3643_MODE_STANDBY);
	if (chip->enable_gpio)
		gpiod_set_value_cansleep(chip->enable_gpio, 0);
}

static const struct i2c_device_id lm3643_id[] = {
	{ "lm3643", 0 },
	{ }
};
MODULE_DEVICE_TABLE(i2c, lm3643_id);

#ifdef CONFIG_ACPI
static const struct acpi_device_id lm3643_acpi_match[] = {
	{ "TXNW3643", 0 },
	{ }
};
MODULE_DEVICE_TABLE(acpi, lm3643_acpi_match);
#endif

static struct i2c_driver lm3643_driver = {
	.driver = {
		.name = LM3643_NAME,
		.acpi_match_table = ACPI_PTR(lm3643_acpi_match),
	},
	.probe = lm3643_probe,
	.remove = lm3643_remove,
	.id_table = lm3643_id,
};

module_i2c_driver(lm3643_driver);

MODULE_DESCRIPTION("Texas Instruments LM3643 Dual Flash LED Driver (ACPI TXNW3643)");
MODULE_AUTHOR("Google Antigravity");
MODULE_LICENSE("GPL v2");
